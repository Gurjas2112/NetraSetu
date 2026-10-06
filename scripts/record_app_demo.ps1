# Records a single-browser walkthrough to results/demo-recording/ (gitignored).
# Requires: .venv, web/node_modules, scripts/dev_platform.py already run or reachable DB.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Missing .venv - see README Quick start."
}

Write-Host "Ensuring platform is up..."
.\.venv\Scripts\python.exe scripts/dev_platform.py postgres garage

$env:PYTHON = "$PWD\.venv\Scripts\python.exe"
$env:DEMO_RECORD = "1"
New-Item -ItemType Directory -Force results\demo-recording | Out-Null

Push-Location web
try {
    npx playwright test demo-walkthrough
} finally {
    Pop-Location
}

$videos = Get-ChildItem -Path ..\results\demo-recording -Recurse -Filter "*.webm" -ErrorAction SilentlyContinue
if ($videos.Count -eq 0) {
    throw "No .webm found under results/demo-recording"
}
$dest = Join-Path $PWD "..\results\demo-recording\NetraSetu-app-walkthrough.webm"
Copy-Item -Force $videos[0].FullName $dest
Write-Host "Saved demo video: $dest"
