"""Verify matlab/config/threshold.json against the hash recorded by eval/.

The hash is SHA-256 of the file's raw bytes, prefixed with 'sha256:'. The same
bytes are hashed in nx_config.m. This module never invents a threshold.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
THRESHOLD = REPO / "matlab" / "config" / "threshold.json"
VALIDATION = REPO / "results" / "validation.json"


def cfg_hash(path: Path = THRESHOLD) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    digest = cfg_hash()
    print(digest)
    if not VALIDATION.is_file():
        print("results/validation.json is absent; hash printed, not compared")
        return 0
    recorded = json.loads(VALIDATION.read_text(encoding="utf-8")).get("cfgHash")
    if recorded != digest:
        print(f"MISMATCH: validation.json cfgHash={recorded}")
        return 1
    print("OK: threshold.json matches results/validation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
