"""Bring up the Tier 0 platform for development and CI, idempotently.

1. Create or complete the gitignored .env: missing keys get defaults, and missing secrets get
   fresh random values. Existing values are never changed and no secret is printed.
2. Write platform/garage/garage.toml if it is missing.
3. `docker compose up -d --wait` for the requested services (default: all).
4. Initialise Garage (layout, bucket, key, CORS) and run the database migrations.

Usage: python scripts/dev_platform.py [service ...]
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
sys.path.insert(0, str(ROOT))

from scripts import garage_init  # noqa: E402

POSTGRES_PORT = "5433"

DEFAULTS = {
    "KEYCLOAK_TAG": "26.4.0",
    "KEYCLOAK_ADMIN": "admin",
    "OIDC_ISSUER": "http://localhost:8080/realms/netrasetu",
    "OIDC_AUDIENCE": "netrasetu-gateway",
    "POSTGRES_USER": "netrasetu",
    "POSTGRES_DB": "netrasetu",
    "POSTGRES_PORT": POSTGRES_PORT,
    "PROMETHEUS_TAG": "v3.5.0",
    "GRAFANA_TAG": "12.1.0",
    "GATEWAY_ENGINE": "fake",
    "GATEWAY_MODE": "inprocess",
    "CORS_ORIGINS": "http://localhost:5173",
    "PRESIGN_TTL_SECONDS": "3600",
}
SECRETS = (
    "KEYCLOAK_ADMIN_PASSWORD",
    "POSTGRES_PASSWORD",
    "GATEWAY_DB_PASSWORD",
    "WORKER_DB_PASSWORD",
    "PATIENT_TOKEN_SECRET",
)


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.partition("=")
            if sep and not key.lstrip().startswith("#"):
                values[key.strip()] = value.strip()
    return values


def ensure_env() -> dict[str, str]:
    values = read_env()
    added: dict[str, str] = {}
    for key, value in DEFAULTS.items():
        if not values.get(key):
            added[key] = value
    for key in SECRETS:
        if not values.get(key):
            added[key] = secrets.token_hex(32)
    merged = {**values, **added}
    port = merged.get("POSTGRES_PORT", POSTGRES_PORT)
    db = merged["POSTGRES_DB"]
    if not values.get("ADMIN_DATABASE_URL"):
        added["ADMIN_DATABASE_URL"] = (
            f"postgresql://{quote(merged['POSTGRES_USER'])}:"
            f"{quote(merged['POSTGRES_PASSWORD'])}@127.0.0.1:{port}/{db}"
        )
    if not values.get("DATABASE_URL"):
        added["DATABASE_URL"] = (
            f"postgresql://gateway:{quote(merged['GATEWAY_DB_PASSWORD'])}@127.0.0.1:{port}/{db}"
        )
    if added:
        lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
        present = {line.partition("=")[0].strip() for line in lines}
        kept = [ln for ln in lines if ln.partition("=")[0].strip() not in added or ln.strip() == ""]
        kept += [f"{k}={v}" for k, v in added.items()]
        ENV.write_text("\n".join(kept) + "\n", encoding="utf-8", newline="\n")
        filled = sorted(k for k in added if k in present)
        new = sorted(k for k in added if k not in present)
        print(f".env: added {', '.join(new) or 'nothing'}; filled {', '.join(filled) or 'nothing'}")
    return read_env()


def main(services: list[str]) -> None:
    env = ensure_env()
    os.environ.update({k: v for k, v in env.items() if k not in os.environ})
    garage_init.ensure_config()
    subprocess.run(["docker", "compose", "up", "-d", "--wait", *services], cwd=ROOT, check=True)
    if not services or "garage" in services:
        garage_init.main()
    if not services or "postgres" in services:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "migrate.py")],
            cwd=ROOT,
            env={**os.environ, **read_env()},
            check=True,
        )


if __name__ == "__main__":
    main(sys.argv[1:])
