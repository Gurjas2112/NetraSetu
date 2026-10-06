"""OIDC bearer-token verification against the Keycloak realm, and role guards.

Keys come from the realm JWKS, cached for JWKS_CACHE_SECONDS and refetched when a token names
an unknown `kid` (Keycloak key rotation). Refetches on unknown kids are rate limited so a
stream of forged tokens cannot turn the gateway into a JWKS amplifier.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

ROLES = frozenset({"screener", "grader", "admin", "patient"})
ALGORITHMS = ["RS256"]
LEEWAY_SECONDS = 30
UNKNOWN_KID_REFETCH_SECONDS = 30

JwksFetcher = Callable[[], dict[str, Any]]


def http_jwks_fetcher(url: str, timeout: float = 5.0) -> JwksFetcher:
    def fetch() -> dict[str, Any]:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read())

    return fetch


class JwksCache:
    def __init__(self, fetch: JwksFetcher, ttl_seconds: int) -> None:
        self._fetch = fetch
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at = 0.0

    def _refresh(self) -> None:
        jwks = self._fetch()
        keys: dict[str, jwt.PyJWK] = {}
        for raw in jwks.get("keys", []):
            if raw.get("use", "sig") != "sig" or "kid" not in raw:
                continue
            try:
                keys[raw["kid"]] = jwt.PyJWK(raw)
            except jwt.PyJWKError:
                continue
        self._keys = keys
        self._fetched_at = time.monotonic()

    def get(self, kid: str) -> jwt.PyJWK | None:
        with self._lock:
            age = time.monotonic() - self._fetched_at
            if not self._keys or age > self._ttl:
                self._refresh()
            elif kid not in self._keys and age > UNKNOWN_KID_REFETCH_SECONDS:
                self._refresh()
            return self._keys.get(kid)


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]
    facility_id: UUID
    hpr_id: str | None
    otp_verified: bool

    @property
    def actor(self) -> str:
        return f"{'+'.join(sorted(self.roles))}:{self.hpr_id or self.subject}"


class TokenVerifier:
    def __init__(self, jwks: JwksCache, issuer: str, audience: str) -> None:
        self._jwks = jwks
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> Principal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise _unauthorized("malformed token") from exc
        kid = header.get("kid")
        if not isinstance(kid, str) or header.get("alg") not in ALGORITHMS:
            raise _unauthorized("unsupported token")
        try:
            key = self._jwks.get(kid)
        except OSError as exc:
            raise HTTPException(503, "identity provider unavailable") from exc
        if key is None:
            raise _unauthorized("unknown signing key")
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                leeway=LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise _unauthorized("invalid token") from exc
        return _principal(claims)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


def _principal(claims: dict[str, Any]) -> Principal:
    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    roles = frozenset(r for r in realm_roles if r in ROLES)
    if not roles:
        raise HTTPException(403, "no NetraSetu role")
    if {"grader", "admin"} <= roles:
        raise HTTPException(403, "grader and admin roles must belong to separate accounts")
    try:
        facility_id = UUID(str(claims["facility_id"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(403, "token has no facility") from exc
    amr = claims.get("amr") or []
    hpr = claims.get("hpr_id")
    return Principal(
        subject=str(claims["sub"]),
        roles=roles,
        facility_id=facility_id,
        hpr_id=str(hpr) if hpr else None,
        otp_verified=isinstance(amr, list) and "otp" in amr,
    )


_bearer = HTTPBearer(auto_error=False)


def current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("bearer token required")
    verifier: TokenVerifier = request.app.state.verifier
    return verifier.verify(credentials.credentials)


def require_role(*allowed: str, totp: bool = False) -> Callable[..., Principal]:
    def guard(principal: Annotated[Principal, Depends(current_principal)]) -> Principal:
        if not principal.roles & set(allowed):
            raise HTTPException(403, "role not permitted")
        if totp and not principal.otp_verified:
            raise HTTPException(403, "this action requires a TOTP-verified session")
        return principal

    return guard
