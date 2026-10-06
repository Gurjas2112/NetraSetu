# Tier 0 demo: platform, synthetic programme seed, gateway health check, web on all interfaces.
# Run from the repository root (for example C:\dev\netrasetu).

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Import-DotEnv {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim()
        }
    }
}

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Create the venv first (see README.md Quick start)."
}

Write-Host "Starting platform (Postgres, Keycloak, Garage, Prometheus, Grafana)..."
.\.venv\Scripts\python.exe scripts/dev_platform.py
.\.venv\Scripts\python.exe scripts/seed_demo.py

Import-DotEnv (Join-Path $PSScriptRoot ".env")
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

Write-Host "Starting gateway on http://0.0.0.0:8000 ..."
$gateway = Start-Process -FilePath $py -WorkingDirectory $PSScriptRoot -PassThru -WindowStyle Hidden `
    -ArgumentList @("-m", "uvicorn", "service.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000")

$healthy = $false
for ($i = 0; $i -lt 60; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/healthz" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $healthy = $true; break }
    } catch {
        Start-Sleep -Seconds 1
    }
}
if (-not $healthy) {
    Stop-Process -Id $gateway.Id -Force -ErrorAction SilentlyContinue
    throw "Gateway did not become healthy at /healthz within 60 seconds."
}
Write-Host "Gateway healthy (engine=$($resp.Content))"

Write-Host "Starting web dev server on http://0.0.0.0:5173 (new window)..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "Set-Location '$PSScriptRoot\web'; npm run dev -- --host"
)

Write-Host ""
Write-Host "Tier 0 demo is up:"
Write-Host "  Gateway   http://127.0.0.1:8000/healthz"
Write-Host "  Web       http://127.0.0.1:5173"
Write-Host "  Grafana   http://127.0.0.1:3000"
Write-Host "  Keycloak  http://127.0.0.1:8080"
Write-Host ""
Write-Host "Gateway PID $($gateway.Id) runs hidden in this session. Stop it with: Stop-Process -Id $($gateway.Id)"
