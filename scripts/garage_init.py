"""Initialise single-node Garage and print S3 credentials for .env.

Every Garage command goes through `docker compose exec`, because the image has no shell.
If platform/garage/garage.toml is missing, it is created from the example with fresh
secrets. That file is gitignored.

CORS is applied with the S3 PutBucketCors API. Garage 2.3 has no `garage bucket cors`
subcommand; the documented way to set it is the S3 API.

Usage: python scripts/garage_init.py
"""

from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOML = ROOT / "platform" / "garage" / "garage.toml"
EXAMPLE = ROOT / "platform" / "garage" / "garage.toml.example"
BUCKET = "netrasetu"
KEY_NAME = "netrasetu-app"


def ensure_config() -> None:
    if TOML.exists():
        return
    text = EXAMPLE.read_text(encoding="utf-8")
    text = text.replace("PASTE_64_HEX_CHARS", secrets.token_hex(32), 1)
    text = text.replace("PASTE_TOKEN", secrets.token_hex(32), 1)
    text = text.replace("PASTE_TOKEN", secrets.token_hex(32), 1)
    if "PASTE_" in text:
        raise SystemExit("garage.toml.example still has an unfilled placeholder")
    TOML.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {TOML} (gitignored; not printed)")


def garage(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", "compose", "exec", "-T", "garage", "/garage", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def node_id() -> str:
    status = garage("status")
    for line in status.stdout.splitlines():
        match = re.match(r"^([0-9a-f]{16,})\b", line.strip())
        if match:
            return match.group(1)
    print(status.stdout, file=sys.stderr)
    raise SystemExit("could not parse a node id from `garage status`")


def ensure_layout(node: str) -> None:
    show = garage("layout", "show", check=False)
    if "No nodes currently have a role" not in show.stdout:
        print("layout already applied")
        return
    staged = garage("layout", "assign", "-z", "dc1", "-c", "20G", node, check=False)
    print((staged.stdout or staged.stderr).strip())
    current = re.search(r"Current cluster layout version:\s*(\d+)", show.stdout)
    version = int(current.group(1)) + 1 if current else 1
    applied = garage("layout", "apply", "--version", str(version))
    print(applied.stdout.strip())


def ensure_bucket() -> None:
    listing = garage("bucket", "list", check=False)
    if BUCKET in listing.stdout.split():
        print(f"bucket {BUCKET} already exists")
        return
    created = garage("bucket", "create", BUCKET)
    print(created.stdout.strip())


def ensure_key() -> tuple[str, str | None]:
    info = garage("key", "info", KEY_NAME, check=False)
    if info.returncode == 0:
        match = re.search(r"Key ID:\s*(\S+)", info.stdout)
        if not match:
            print(info.stdout, file=sys.stderr)
            raise SystemExit("key exists but its id could not be parsed")
        print("key already exists; the secret is shown only at creation")
        return match.group(1), None
    created = garage("key", "create", KEY_NAME)
    print(created.stdout.strip())
    key_id = re.search(r"Key ID:\s*(\S+)", created.stdout)
    secret = re.search(r"Secret key:\s*(\S+)", created.stdout)
    if not key_id or not secret:
        raise SystemExit("could not parse the new access key")
    return key_id.group(1), secret.group(1)


def allow(key_id: str) -> None:
    result = garage("bucket", "allow", "--read", "--write", "--owner", BUCKET, "--key", key_id)
    print(result.stdout.strip())


def put_cors(key_id: str, secret: str) -> None:
    import boto3
    from botocore.config import Config

    origins = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ]
    client = boto3.client(
        "s3",
        endpoint_url=os.environ.get("S3_ENDPOINT", "http://127.0.0.1:3900"),
        region_name=os.environ.get("S3_REGION", "garage"),
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        config=Config(s3={"addressing_style": "path"}),
    )
    client.put_bucket_cors(
        Bucket=BUCKET,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": origins,
                    "AllowedMethods": ["GET", "HEAD", "PUT"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": 3600,
                }
            ]
        },
    )
    print(f"cors set for {', '.join(origins)}")


def env_file_value(name: str) -> str | None:
    path = ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key == name and value.strip():
            return value.strip()
    return None


def write_env(key_id: str, secret: str | None) -> None:
    """Fill storage keys in the gitignored .env. Never prints the secret."""
    env_path = ROOT / ".env"
    if secret is None or not env_path.exists():
        return
    updates = {
        "S3_ENDPOINT": "http://127.0.0.1:3900",
        "S3_REGION": "garage",
        "S3_BUCKET": BUCKET,
        "S3_ACCESS_KEY": key_id,
        "S3_SECRET_KEY": secret,
    }
    lines = env_path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    rewritten: list[str] = []
    for line in lines:
        key, sep, _value = line.partition("=")
        if sep and key in updates:
            rewritten.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            rewritten.append(line)
    for key, value in updates.items():
        if key not in seen:
            rewritten.append(f"{key}={value}")
    env_path.write_text("\n".join(rewritten) + "\n", encoding="utf-8", newline="\n")
    print("updated .env storage keys")


def main() -> None:
    ensure_config()
    ensure_layout(node_id())
    ensure_bucket()
    key_id, secret = ensure_key()
    allow(key_id)
    if secret is None:
        secret = os.environ.get("S3_SECRET_KEY", "").strip() or env_file_value("S3_SECRET_KEY")
    if secret:
        put_cors(key_id, secret)
        write_env(key_id, secret)
    else:
        print("cors skipped: secret is not available. Re-run with S3_SECRET_KEY set.")
    print()
    print("Storage settings, for .env:")
    print("S3_ENDPOINT=http://127.0.0.1:3900")
    print("S3_REGION=garage")
    print(f"S3_BUCKET={BUCKET}")
    print(f"S3_ACCESS_KEY={key_id}")
    if secret and not (ROOT / ".env").exists():
        print(f"S3_SECRET_KEY={secret}")
    elif secret:
        print("S3_SECRET_KEY written to .env")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or exc.stdout, file=sys.stderr)
        sys.exit(exc.returncode)
