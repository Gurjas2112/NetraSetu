# Tier 1 deploy helper (Supabase dashboard + Railway + Vercel). Does not commit secrets.
# Prereqs: supabase project (Mumbai), railway login, vercel login, .env.tier1 filled from README.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".env.tier1")) {
    Write-Host @"
Create .env.tier1 from .env.example with Tier 1 values:
  ADMIN_DATABASE_URL  — Supabase session pooler (5432), admin role for migrate
  DATABASE_URL        — gateway role on same pooler
  S3_*                — Supabase Storage S3-compatible endpoint
  CORS_ORIGINS        — https://<your-vercel-domain>
Then re-run this script.
"@ -ForegroundColor Yellow
    exit 1
}

Get-Content .env.tier1 | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}

Write-Host "Applying migrations to Supabase (ADMIN_DATABASE_URL)..."
.\.venv\Scripts\python.exe scripts/migrate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building gateway image (smoke)..."
docker build -f service/Dockerfile.gateway -t netrasetu-gateway:local .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Get-Command railway -ErrorAction SilentlyContinue)) {
    Write-Host "Install Railway CLI (Scoop: scoop install railway), then: railway login && railway init && railway up" -ForegroundColor Yellow
} else {
    railway whoami 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Run: railway login" -ForegroundColor Yellow
    } else {
        Write-Host "Deploy gateway: railway up (from repo root; set variables per README Tier 1)"
    }
}

Push-Location web
try {
    vercel whoami 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Run: vercel login && vercel link" -ForegroundColor Yellow
    } else {
        Write-Host "Deploy web: vercel --prod (set VITE_API_BASE / OIDC env in Vercel dashboard)"
        vercel --prod
    }
} finally {
    Pop-Location
}

Write-Host @"

MATLAB (Tier 1 grader on laptop — not on Railway):
  1. matlab.engine.shareEngine('netrasetu') in MATLAB R2026b
  2. `$env:GATEWAY_ENGINE='matlab'; `$env:DATABASE_URL=<worker pooler DSN>; python -m service.worker

GitHub: add secret SUPABASE_KEEPALIVE_URL for .github/workflows/keepalive.yml
"@
