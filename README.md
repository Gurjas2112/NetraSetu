# NetraSetu

NetraSetu is an explainable diabetic-retinopathy (DR) screening system for primary health centres
in rural India (Smart India Hackathon PS 26038, MathWorks). A field worker captures a fundus image;
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

The gateway reads its configuration from the environment; load `.env` first (for example with
your shell or IDE), or use the test suites below, which load it themselves. Every route except
`/healthz`, `/metrics` and `/r/{token}` needs a Keycloak access token (see docs/CONTRACT.md); the
web client gets one from the login flow in M5. Until then the Playwright suite signs its own
test tokens.

Tests:

```powershell
python -m pytest -q           # database tests need the platform from dev_platform.py
npm --prefix web run build

# end-to-end: Playwright starts a test JWKS server, the fake-engine gateway and Vite itself
npx --prefix web playwright install chromium
$env:PYTHON = "$PWD\.venv\Scripts\python.exe"
npm --prefix web run test:e2e
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
matlab -batch "addpath('matlab','matlab/nx'); r = runtests('matlab/tests/unit'); exit(any([r.Failed]))"
New-Item -ItemType Directory -Force results | Out-Null
matlab -batch "addpath('matlab','matlab/nx'); writelines(netrasetu_analyze_json('tests/fixtures/grade2_haem.png', tempdir), 'results/stub.json')"
python -m service.validate_json results/stub.json
```

To serve it, run `matlab.engine.shareEngine("netrasetu")` in an open MATLAB R2026b session,
install `matlabengine` from `requirements.txt`, and start the gateway with
`GATEWAY_ENGINE=matlab` and `MATLAB_SHARED_ENGINE=netrasetu`.

## Documentation

- Build rules for contributors and agents: [`AGENTS.md`](AGENTS.md)
- Specifications: [`docs/spec/`](docs/spec/)
- Engine and API contract: [`docs/CONTRACT.md`](docs/CONTRACT.md)
- Validation template: [`docs/VALIDATION.md`](docs/VALIDATION.md)
- Known limitations: [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)
