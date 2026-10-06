"""Gateway configuration read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[1]

EngineKind = Literal["fake", "matlab"]
GatewayMode = Literal["inprocess", "queue"]


class SettingsError(ValueError):
    """A required setting is missing or malformed."""


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def _required(name: str) -> str:
    value = _env(name)
    if not value:
        raise SettingsError(f"{name} must be set (see .env.example)")
    return value


def _bool(name: str, default: bool) -> bool:
    value = _env(name)
    if not value:
        return default
    if value.lower() in ("1", "true", "yes", "on"):
        return True
    if value.lower() in ("0", "false", "no", "off"):
        return False
    raise SettingsError(f"{name} must be true or false, got {value!r}")


def _int(name: str, default: int) -> int:
    value = _env(name)
    if not value:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise SettingsError(f"{name} must be an integer, got {value!r}") from exc
    if parsed <= 0:
        raise SettingsError(f"{name} must be positive")
    return parsed


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class S3Settings:
    endpoint: str
    region: str
    bucket: str
    access_key: str
    secret_key: str


@dataclass(frozen=True)
class Settings:
    engine: EngineKind
    database_url: str
    oidc_issuer: str
    oidc_audience: str
    patient_token_secret: str
    s3: S3Settings
    gateway_mode: GatewayMode = "inprocess"
    matlab_shared_engine: str = "netrasetu"
    nx_root: Path = REPO_ROOT / "matlab"
    work_dir: Path = REPO_ROOT / "results" / "work"
    cors_origins: list[str] = field(default_factory=list)
    max_upload_bytes: int = 25 * 1024 * 1024
    cache_enabled: bool = True
    cached_mode: bool = False
    idempotency_ttl_days: int = 7
    presign_ttl_seconds: int = 3600
    jwks_cache_seconds: int = 3600
    patient_token_hours: int = 72

    @property
    def threshold_path(self) -> Path:
        return self.nx_root / "config" / "threshold.json"

    @property
    def jwks_url(self) -> str:
        return self.oidc_issuer.rstrip("/") + "/protocol/openid-connect/certs"


def load_settings() -> Settings:
    engine = _env("GATEWAY_ENGINE", "fake")
    if engine not in ("fake", "matlab"):
        raise SettingsError(f"GATEWAY_ENGINE must be 'fake' or 'matlab', got {engine!r}")
    mode = _env("GATEWAY_MODE", "inprocess")
    if mode not in ("inprocess", "queue"):
        raise SettingsError(f"GATEWAY_MODE must be 'inprocess' or 'queue', got {mode!r}")
    secret = _required("PATIENT_TOKEN_SECRET")
    if len(secret) < 32:
        raise SettingsError("PATIENT_TOKEN_SECRET must be at least 32 characters")
    return Settings(
        engine=engine,  # type: ignore[arg-type]
        gateway_mode=mode,  # type: ignore[arg-type]
        database_url=_required("DATABASE_URL"),
        oidc_issuer=_required("OIDC_ISSUER"),
        oidc_audience=_required("OIDC_AUDIENCE"),
        patient_token_secret=secret,
        s3=S3Settings(
            endpoint=_required("S3_ENDPOINT"),
            region=_env("S3_REGION", "garage"),
            bucket=_required("S3_BUCKET"),
            access_key=_required("S3_ACCESS_KEY"),
            secret_key=_required("S3_SECRET_KEY"),
        ),
        matlab_shared_engine=_env("MATLAB_SHARED_ENGINE", "netrasetu"),
        nx_root=Path(_env("NX_ROOT", str(REPO_ROOT / "matlab"))),
        cors_origins=_csv(_env("CORS_ORIGINS", "http://localhost:5173")),
        cache_enabled=_bool("CACHE_ENABLED", True),
        cached_mode=_bool("NX_CACHED_MODE", False),
        idempotency_ttl_days=_int("IDEMPOTENCY_TTL_DAYS", 7),
        presign_ttl_seconds=_int("PRESIGN_TTL_SECONDS", 3600),
        jwks_cache_seconds=_int("JWKS_CACHE_SECONDS", 3600),
    )
