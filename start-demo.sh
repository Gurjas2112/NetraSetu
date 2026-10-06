#!/usr/bin/env bash
# Tier 0 demo: platform, synthetic programme seed, gateway health check, web on all interfaces.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Create the venv first (see README.md Quick start)." >&2
  exit 1
fi

PY="$ROOT/.venv/bin/python"

echo "Starting platform (Postgres, Keycloak, Garage, Prometheus, Grafana)..."
"$PY" scripts/dev_platform.py
"$PY" scripts/seed_demo.py

set -a
# shellcheck disable=SC1091
[[ -f .env ]] && source .env
set +a

echo "Starting gateway on http://0.0.0.0:8000 ..."
"$PY" -m uvicorn service.main:create_app --factory --host 0.0.0.0 --port 8000 &
GW_PID=$!
cleanup() { kill "$GW_PID" 2>/dev/null || true; }
trap cleanup EXIT

healthy=0
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/healthz >/dev/null; then
    healthy=1
    break
  fi
  sleep 1
done
if [[ "$healthy" -ne 1 ]]; then
  echo "Gateway did not become healthy at /healthz within 60 seconds." >&2
  exit 1
fi
echo "Gateway healthy."

echo "Starting web dev server on http://0.0.0.0:5173 (foreground; Ctrl+C stops web only)..."
cd web
npm run dev -- --host
