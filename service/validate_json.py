"""Validate engine JSON (contract 6.1) against service/schemas.py.

Usage:
    python -m service.validate_json result.json
    <command producing JSON> | python -m service.validate_json -
"""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import ValidationError

from service.schemas import EngineResult


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    source = argv[1]
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    try:
        result = EngineResult.model_validate_json(text)
    except ValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"OK: contract {result.contractVersion}, decision {result.decision}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
