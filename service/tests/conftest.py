"""Shared fixtures: a migrated database, RS256 test tokens, and gateway apps on MemoryStorage.

Database-backed tests are skipped unless ADMIN_DATABASE_URL is set; a local `.env` is read
first (without overriding the environment) so `pytest` works after `scripts/dev_platform.py`.
"""

from __future__ import annotations

import io
import os
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import jwt
import numpy as np
import psycopg
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from PIL import Image
from psycopg.rows import dict_row

from service.cache import Services
from service.engine import Engine, FakeEngine
from service.main import create_app
from service.settings import REPO_ROOT, S3Settings, Settings
from service.storage import MemoryStorage

THRESHOLD = REPO_ROOT / "matlab" / "config" / "threshold.json"
ISSUER = "https://idp.test/realms/netrasetu"
AUDIENCE = "netrasetu-gateway"
KID = "test-signing-key"
PATIENT_TOKEN_SECRET = "test-only-patient-token-secret-0123456789"


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(REPO_ROOT / ".env")


def role_url(admin_url: str, user: str, password: str) -> str:
    parts = urlsplit(admin_url)
    host = parts.hostname or "localhost"
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, f"{quote(user)}:{quote(password)}@{host}", parts.path, "", ""))


def run_migrate() -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "migrate.py")],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="session")
def admin_url() -> str:
    url = os.environ.get("ADMIN_DATABASE_URL")
    if not url:
        pytest.skip("ADMIN_DATABASE_URL is not set")
    result = run_migrate()
    assert result.returncode == 0, result.stderr
    return url


@pytest.fixture(scope="session")
def gateway_url(admin_url: str) -> str:
    return role_url(admin_url, "gateway", os.environ["GATEWAY_DB_PASSWORD"])


@pytest.fixture(scope="session")
def worker_url(admin_url: str) -> str:
    return role_url(admin_url, "worker", os.environ["WORKER_DB_PASSWORD"])


@pytest.fixture
def admin_db(admin_url: str) -> Iterator[psycopg.Connection[dict]]:
    with psycopg.connect(admin_url, autocommit=True, row_factory=dict_row) as conn:
        yield conn


# --- tokens -------------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def jwks(signing_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key(), as_dict=True)
    return {"keys": [{**jwk, "kid": KID, "use": "sig", "alg": "RS256"}]}


Mint = Callable[..., dict[str, str]]


@pytest.fixture(scope="session")
def mint(signing_key: rsa.RSAPrivateKey) -> Mint:
    """mint(roles, facility, otp=False, hpr=None, **claim overrides) -> Authorization header."""

    def _mint(
        roles: str | list[str],
        facility: uuid.UUID | None,
        *,
        otp: bool = False,
        hpr: str | None = None,
        kid: str = KID,
        **overrides: Any,
    ) -> dict[str, str]:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 300,
            "realm_access": {"roles": [roles] if isinstance(roles, str) else roles},
            "amr": ["pwd", "otp"] if otp else ["pwd"],
        }
        if facility is not None:
            claims["facility_id"] = str(facility)
        if hpr:
            claims["hpr_id"] = hpr
        claims.update(overrides)
        token = jwt.encode(claims, signing_key, algorithm="RS256", headers={"kid": kid})
        return {"Authorization": f"Bearer {token}"}

    return _mint


# --- gateway ------------------------------------------------------------------------------------


@dataclass
class Gateway:
    client: TestClient
    services: Services
    storage: MemoryStorage
    engine: Engine


def make_settings(tmp_path: Path, database_url: str, **overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "engine": "fake",
        "database_url": database_url,
        "oidc_issuer": ISSUER,
        "oidc_audience": AUDIENCE,
        "patient_token_secret": PATIENT_TOKEN_SECRET,
        "s3": S3Settings("http://s3.invalid", "garage", "netrasetu", "unused", "unused"),
        "work_dir": tmp_path / "work",
        "cors_origins": ["http://localhost:5173"],
    }
    base.update(overrides)
    return Settings(**base)


GatewayFactory = Callable[..., Gateway]


@pytest.fixture
def gateway_factory(tmp_path: Path, gateway_url: str, jwks: dict[str, Any]) -> GatewayFactory:
    def _make(engine: Engine | None = None, **overrides: Any) -> Gateway:
        settings = make_settings(tmp_path, gateway_url, **overrides)
        storage = MemoryStorage()
        engine = engine or FakeEngine(THRESHOLD)
        app = create_app(settings, engine=engine, storage=storage, jwks_fetch=lambda: jwks)
        return Gateway(TestClient(app), app.state.services, storage, engine)

    return _make


@pytest.fixture
def gateway(gateway_factory: GatewayFactory) -> Gateway:
    return gateway_factory()


def unique_png(size: int = 64) -> bytes:
    """Random pixels, so the global same-image check never links unrelated tests."""
    pixels = np.random.default_rng().integers(0, 256, size=(size, size, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(pixels).save(buf, format="PNG")
    return buf.getvalue()
