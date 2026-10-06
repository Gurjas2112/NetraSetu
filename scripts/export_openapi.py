"""Write the gateway's OpenAPI document to web/src/api/openapi.json for openapi-typescript.

Usage: python scripts/export_openapi.py

The schema is built from placeholder settings; nothing connects to a database, the identity
provider or storage.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from service.engine import FakeEngine  # noqa: E402
from service.main import create_app  # noqa: E402
from service.settings import S3Settings, Settings  # noqa: E402
from service.storage import MemoryStorage  # noqa: E402

OUT = ROOT / "web" / "src" / "api" / "openapi.json"


def openapi_schema() -> dict[str, Any]:
    settings = Settings(
        engine="fake",
        database_url="postgresql://openapi.invalid/none",
        oidc_issuer="https://openapi.invalid/realms/netrasetu",
        oidc_audience="netrasetu-gateway",
        patient_token_secret="openapi-export-placeholder-not-a-secret",
        s3=S3Settings("http://openapi.invalid", "garage", "netrasetu", "none", "none"),
    )
    app = create_app(
        settings,
        engine=FakeEngine(settings.threshold_path),
        storage=MemoryStorage(),
        jwks_fetch=lambda: {"keys": []},
    )
    return app.openapi()


def main() -> None:
    OUT.write_text(
        json.dumps(openapi_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
