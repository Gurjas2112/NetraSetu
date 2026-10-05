# NetraSetu

NetraSetu is an explainable diabetic-retinopathy (DR) screening system for primary health centres
in rural India (Smart India Hackathon PS 26038, MathWorks). A field worker captures a fundus image;
a MATLAB pipeline checks image quality, segments retinal structures and lesions, grades severity on
the International Clinical DR scale, and returns one of three decisions — `REFER`, `ROUTINE` or
`RETAKE` — together with lesion-level evidence, a Grad-CAM map and a calibrated posterior, so that
an ophthalmologist can confirm or overturn each case in seconds.

All algorithms live in MATLAB. Python (FastAPI) is the gateway; the web client is React + Vite.

## Quick start (Tier 0, fake engine — no MATLAB needed)

Requirements: Python 3.12, Node >= 22.12. Keep the clone at a path without spaces
(for example `C:\dev\netrasetu`).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r service/requirements-gateway.txt -r requirements-dev.txt
python scripts/make_fixtures.py

$env:GATEWAY_ENGINE = "fake"
$env:CORS_ORIGINS = "http://localhost:5173"
uvicorn service.main:app --port 8000
```

In a second terminal:

```powershell
npm --prefix web ci
npm --prefix web run dev
```

Open `http://localhost:5173/field` and upload any image from `tests/fixtures/`.

Tests:

```powershell
python -m pytest -q
npm --prefix web run build

# end-to-end: Playwright starts the fake-engine gateway and Vite itself
npx --prefix web playwright install chromium
$env:PYTHON = "$PWD\.venv\Scripts\python.exe"
npm --prefix web run test:e2e
```

After changing `service/schemas.py`, regenerate the client types (never hand-edit them):

```powershell
python scripts/export_openapi.py
npm --prefix web run gen:api
```

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
