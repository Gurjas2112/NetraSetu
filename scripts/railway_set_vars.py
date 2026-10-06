"""Push .env.tier1 keys to the linked Railway service (values never printed)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.tier1"
SKIP = {"ADMIN_DATABASE_URL", "SUPABASE_KEEPALIVE_URL", "WORKER_DB_PASSWORD"}


def main() -> int:
    if not ENV_FILE.is_file():
        print("Missing .env.tier1 — run scripts/setup_tier1_supabase.py first.", file=sys.stderr)
        return 1
    service = os.environ.get("RAILWAY_SERVICE", "").strip()
    pairs: list[tuple[str, str]] = []
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in SKIP:
            continue
        if not value:
            continue
        pairs.append((key, value))
    if not pairs:
        return 1
    for key, value in pairs:
        cmd = ["railway", "variables", "set", f"{key}={value}"]
        if service:
            cmd.extend(["-s", service])
        result = subprocess.run(cmd, cwd=ROOT, check=False)
        if result.returncode != 0:
            print(f"Failed to set {key}", file=sys.stderr)
            return result.returncode
    print(f"Set {len(pairs)} Railway variables from .env.tier1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
