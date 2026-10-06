#!/usr/bin/env sh
# OWASP ZAP baseline against a local gateway. Laptop only — not CI.
# Usage: scripts/zap-baseline.sh [http://host.docker.internal:8000]
set -eu
TARGET="${1:-http://host.docker.internal:8000}"
docker run --rm -t --add-host=host.docker.internal:host-gateway \
    ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t "$TARGET"
