# NetraSetu

NetraSetu is an explainable diabetic-retinopathy (DR) screening system for primary health centres
in rural India . A field worker captures a fundus image;
a MATLAB pipeline checks image quality, segments retinal structures and lesions, grades severity on
the International Clinical DR scale, and returns one of three decisions — `REFER`, `ROUTINE` or
`RETAKE` — together with lesion-level evidence, a Grad-CAM map and a calibrated posterior, so that
an ophthalmologist can confirm or overturn each case in seconds.

All algorithms live in MATLAB. Python (FastAPI) is the gateway; the web client is React + Vite.

## Quick start (Tier 0, fake engine — no MATLAB needed)

Requirements: Python 3.12, Node >= 22.12, Docker. Keep the clone at a path without spaces
(for example `C:\dev\netrasetu`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r service/requirements-gateway.txt -r requirements-dev.txt
python scripts/make_fixtures.py

# Creates or completes the gitignored .env (generated secrets, never printed), starts the
# containers, initialises Garage and runs the migrations. Safe to re-run.
python scripts/dev_platform.py

uvicorn service.main:create_app --factory --port 8000
```

### One-command Tier 0 demo

After the venv and `npm install` under `web/`, from the repository root:

```powershell
.\start-demo.ps1
```

On Linux or macOS: `./start-demo.sh`. The script runs `dev_platform.py`, seeds **30 days of synthetic programme data** across four facilities (`python scripts/seed_demo.py`, idempotent; `--force` replaces prior synthetic rows), starts the gateway on `0.0.0.0:8000`, waits for `/healthz`, then opens the web dev server with `--host` so a phone on the hotspot can reach the laptop. Data is marked `seedDemo` in JSON and `synthetic: true` in audit — not real patients. For camera and offline mode over HTTP on Android, see the product spec Tier 0 runbook (Chrome insecure-origin flag).

**App walkthrough video (local):** `powershell -File scripts/record_app_demo.ps1` writes `results/demo-recording/NetraSetu-app-walkthrough.webm` (gitignored). Requires `npx playwright install chromium` once under `web/`.

The gateway reads its configuration from the environment; load `.env` first (for example with
your shell or IDE), or use the test suites below, which load it themselves. Every route except
`/healthz`, `/metrics` and `/r/{token}` needs a Keycloak access token (see docs/CONTRACT.md); the
web client gets one from the login flow in M5. Until then the Playwright suite signs its own
test tokens.

Tests:

```powershell
python -m pytest -q           # database tests need the platform from dev_platform.py
npm --prefix web run test     # Vitest: posterior band, evidence strip, i18n key parity
npm --prefix web run build

# end-to-end: Playwright starts a test JWKS server, the fake-engine gateway and Vite itself
npx --prefix web playwright install chromium
$env:PYTHON = "$PWD\.venv\Scripts\python.exe"
npm --prefix web run test:e2e
```

Load (laptop, not CI). A running in-process gateway and a screener bearer token are required.
Each request changes one pixel so the inference cache misses and the engine is timed:

```powershell
New-Item -ItemType Directory -Force results | Out-Null
$env:LOCUST_ACCESS_TOKEN = "<screener access token>"
locust -f tests/load/locustfile.py --headless -u 4 -r 1 -t 5m --csv results/load --host http://127.0.0.1:8000
python scripts/locust_to_simevents.py results/load
.\scripts\zap-baseline.ps1
```

`locust_to_simevents.py` copies p50/p95 from the CSV into `matlab/simevents/params.json` (gitignored). Do not type those times by hand.

## Capacity model (SimEvents, HUMAN-VERIFY to simulate)

Copy `matlab/simevents/params.json.example` to `matlab/simevents/params.json`, fill measured rework, cache-hit and triage fractions, then merge Locust inference times. Build the District Twin programmatically (no hand-edited `.slx`):

```powershell
matlab -batch "addpath('matlab/simevents'); build_district_twin; exit"
```

Sanity-check the grader pool with the analytic M/M/c helper (same rate units throughout):

```powershell
matlab -batch "addpath('matlab/simevents'); disp(erlang_check(3, 4, 2)); exit"
```

After changing `service/schemas.py`, regenerate the client types (never hand-edit them):

```powershell
python scripts/export_openapi.py
npm --prefix web run gen:api
```

## Platform (Postgres, Keycloak, Garage, Prometheus, Grafana)

Copy `.env.example` to `.env` and fill it in. `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `KEYCLOAK_ADMIN`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_TAG`, `PROMETHEUS_TAG` and `GRAFANA_TAG` have to be set before Compose will start. Pin exact image tags; do not use `latest`. Postgres is published on `${POSTGRES_PORT:-5432}`. Set `POSTGRES_PORT` if something else on the machine already listens on 5432, and use that port in `ADMIN_DATABASE_URL`.

`python scripts/garage_init.py` writes `platform/garage/garage.toml` (gitignored) if it is missing, then assigns the Garage layout, creates the bucket and key, and prints `S3_ACCESS_KEY` / `S3_SECRET_KEY` for `.env`. Start Compose first so the Garage container is up before that second step; the script creates the toml on its own, so a first run that fails at `docker compose exec` still leaves a config you can boot with.

```powershell
python scripts/garage_init.py
docker compose up -d --wait
python scripts/garage_init.py
python scripts/migrate.py
python scripts/migrate.py
```

The second `migrate.py` prints `applied nothing`. `python scripts/dev_platform.py [service ...]`
does all of this in one step (CI runs it with `postgres garage`).

## Using the real MATLAB engine

Check the stub contract from the repository root:

```powershell
matlab -batch "addpath('matlab','matlab/nx'); r = runtests('matlab/tests', 'IncludeSubfolders', true); disp(table(r)); exit(any([r.Failed]))"
New-Item -ItemType Directory -Force results | Out-Null
matlab -batch "addpath('matlab','matlab/nx'); writelines(netrasetu_analyze_json('tests/fixtures/grade2_haem.png', tempdir), 'results/stub.json')"
python -m service.validate_json results/stub.json
python eval/check_threshold_hash.py
```

Training (`matlab/train/*.m`) and `eval/run_validation.m` need local datasets under `data/` (never committed) and write `results/validation.json` on this machine only.

To serve it, run `matlab.engine.shareEngine("netrasetu")` in an open MATLAB R2026b session,
install `matlabengine` from `requirements.txt`, and start the gateway with
`GATEWAY_ENGINE=matlab` and `MATLAB_SHARED_ENGINE=netrasetu`.

## Tier 1 showcase (Vercel · Railway · Supabase Mumbai)

Tier 1 is a public link for judges, not a production clinic. Create the three cloud projects by
hand (never commit their secrets). Pick **South Asia (Mumbai)** (`ap-south-1`) when you create
the Supabase project — the region cannot be changed afterwards.

Connect both the Railway gateway and the laptop worker through the **session pooler on port
5432**, never the transaction pooler on 6543. Transaction mode does not support prepared
statements; psycopg starts preparing the claim query automatically, and the worker would fail
after a few polls. The gateway uses the `gateway` role DSN; the worker uses the `worker` role
DSN (`WORKER_DB_PASSWORD`) as `DATABASE_URL`.

```powershell
# Supabase schema + .env.tier1 (session pooler, never commit):
#   set SUPABASE_DB_PASSWORD / S3 keys / service role, then:
python scripts/setup_tier1_supabase.py

# Railway project netrasetu_app_backend (da130793-430e-410d-aef2-72521037b1dd):
# Create services keycloak + gateway, then:
#   $env:RAILWAY_TOKEN = '<from railway.app/account/tokens>'
powershell -File scripts/railway_deploy.ps1

docker build -f service/Dockerfile.gateway .
# Railway: GATEWAY_MODE=queue, GATEWAY_ENGINE=fake (or matlab only if a worker is pulling)

# Laptop worker — outbound only; no tunnel
$env:GATEWAY_ENGINE = "matlab"
python -m service.worker
```

`web/vercel.json` rewrites the SPA and sets `Referrer-Policy: no-referrer`,
`Permissions-Policy: camera=(self), microphone=()`, and `Cache-Control: no-cache` on `sw.js`.
Daily keepalive is `.github/workflows/keepalive.yml`: store the session-pooler URI as the GitHub
secret `SUPABASE_KEEPALIVE_URL` (not in `.env`). A paused free project will otherwise sleep
before a demo.

## Documentation

- Build rules for contributors and agents: [`AGENTS.md`](AGENTS.md)
- Specifications: [`docs/spec/`](docs/spec/)
- Engine and API contract: [`docs/CONTRACT.md`](docs/CONTRACT.md)
- Validation template: [`docs/VALIDATION.md`](docs/VALIDATION.md)
- Known limitations: [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)
