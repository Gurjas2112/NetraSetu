"""Patient link tokens: HMAC-signed, single use, 72 h, bound to one study and one phone hash.

The signature makes tokens unforgeable; the `clinical.patient_token` row makes them single use.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

_DOMAIN = b"netrasetu.patient-token.v1:"


def _b64e(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


@dataclass(frozen=True)
class PatientToken:
    jti: UUID
    study_id: UUID
    phone_hash: bytes
    expires_at: int


class TokenInvalid(ValueError):
    """Not a token we issued."""


class TokenExpired(ValueError):
    """A genuine token past its lifetime."""


def mint(
    secret: str, study_id: UUID, phone_hash: bytes, lifetime_seconds: int
) -> tuple[str, PatientToken]:
    tok = PatientToken(
        jti=uuid4(),
        study_id=study_id,
        phone_hash=phone_hash,
        expires_at=int(time.time()) + lifetime_seconds,
    )
    body = _b64e(
        json.dumps(
            {
                "jti": str(tok.jti),
                "sid": str(tok.study_id),
                "ph": tok.phone_hash.hex(),
                "exp": tok.expires_at,
            },
            separators=(",", ":"),
        ).encode()
    )
    sig = hmac.new(secret.encode(), _DOMAIN + body.encode(), hashlib.sha256).digest()
    return f"{body}.{_b64e(sig)}", tok


def verify(secret: str, token: str, now: float | None = None) -> PatientToken:
    try:
        body, sig = token.split(".")
        expected = hmac.new(secret.encode(), _DOMAIN + body.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64d(sig)):
            raise TokenInvalid("bad signature")
        data = json.loads(_b64d(body))
        tok = PatientToken(
            jti=UUID(data["jti"]),
            study_id=UUID(data["sid"]),
            phone_hash=bytes.fromhex(data["ph"]),
            expires_at=int(data["exp"]),
        )
    except TokenInvalid:
        raise
    except (ValueError, KeyError, TypeError) as exc:
        raise TokenInvalid("malformed token") from exc
    if (now if now is not None else time.time()) >= tok.expires_at:
        raise TokenExpired("token expired")
    return tok
