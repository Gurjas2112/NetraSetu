"""Write the gateway's OpenAPI document to web/src/api/openapi.json for openapi-typescript.

Usage: python scripts/export_openapi.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GATEWAY_ENGINE", "fake")

from service.main import create_app  # noqa: E402

OUT = ROOT / "web" / "src" / "api" / "openapi.json"


def main() -> None:
    schema = create_app().openapi()
    OUT.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
