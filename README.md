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
npm --prefix web run test:e2e
```

## Using the real MATLAB engine

In MATLAB R2026b, add `matlab/` and `matlab/nx/` to the path and run
`matlab.engine.shareEngine("netrasetu")`. Install `matlabengine` from `requirements.txt` and start
the gateway with `GATEWAY_ENGINE=matlab` and `MATLAB_SHARED_ENGINE=netrasetu`.

## Documentation

- Build rules for contributors and agents: [`AGENTS.md`](AGENTS.md)
- Specifications: [`docs/spec/`](docs/spec/)
- Engine and API contract: [`docs/CONTRACT.md`](docs/CONTRACT.md)
- Validation template: [`docs/VALIDATION.md`](docs/VALIDATION.md)
- Known limitations: [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)
