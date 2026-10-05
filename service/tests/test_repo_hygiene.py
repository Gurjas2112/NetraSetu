import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

REQUIRED_ENV_KEYS = """
KEYCLOAK_TAG KEYCLOAK_ADMIN KEYCLOAK_ADMIN_PASSWORD OIDC_ISSUER OIDC_AUDIENCE
POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB ADMIN_DATABASE_URL DATABASE_URL
GATEWAY_DB_PASSWORD WORKER_DB_PASSWORD
S3_ENDPOINT S3_REGION S3_BUCKET S3_ACCESS_KEY S3_SECRET_KEY PRESIGN_TTL_SECONDS
PROMETHEUS_TAG GRAFANA_TAG
GATEWAY_ENGINE GATEWAY_MODE
MATLAB_SHARED_ENGINE NX_ROOT CORS_ORIGINS NX_CACHED_MODE
CACHE_ENABLED IDEMPOTENCY_TTL_DAYS JWKS_CACHE_SECONDS PATIENT_TOKEN_SECRET
WORKER_ID
VITE_API_BASE VITE_OIDC_ISSUER VITE_OIDC_CLIENT_ID
""".split()


def _env_example_entries() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        entries[key.strip()] = value.strip()
    return entries


def test_env_example_has_every_key() -> None:
    missing = set(REQUIRED_ENV_KEYS) - set(_env_example_entries())
    assert not missing, f".env.example is missing {sorted(missing)}"


def test_env_example_has_no_values() -> None:
    filled = {k: v for k, v in _env_example_entries().items() if v}
    assert not filled, f".env.example must not contain values: {sorted(filled)}"


def test_secrets_are_gitignored() -> None:
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for entry in (".env", ".env.tier1", "garage.toml"):
        assert entry in ignored


def _committable_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if line]


def test_no_supabase_or_jwt_secrets_committed() -> None:
    # Split so this file does not match its own pattern.
    pattern = re.compile("|".join(["sb_" + "secret_", "sb_" + "publishable_", "eyJhbGci" + "Oi"]))
    for path in _committable_files():
        if not path.is_file() or path.suffix.lower() in {".png", ".jpg", ".ico", ".pdf"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not pattern.search(text), f"possible secret in {path.relative_to(ROOT)}"
