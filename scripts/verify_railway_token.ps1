# Quick check: project token vs account token (does not print secrets).
param(
    [string]$ProjectId = "da130793-430e-410d-aef2-72521037b1dd",
    [string]$Environment = "production",
    [string]$Service = "gateway"
)

if ($env:RAILWAY_API_TOKEN -and $env:RAILWAY_TOKEN) {
    Write-Host "Clear RAILWAY_API_TOKEN when testing a project RAILWAY_TOKEN."
    exit 1
}

if ($env:RAILWAY_API_TOKEN) {
    railway whoami
    exit $LASTEXITCODE
}

if (-not $env:RAILWAY_TOKEN) {
    Write-Host "Set RAILWAY_TOKEN or RAILWAY_API_TOKEN first."
    exit 1
}

Write-Host "Project token: skipping whoami (not supported)."
Write-Host "Attempting dry deploy flags..."
railway up -d -p $ProjectId -e $Environment -s $Service -m "token-verify" 2>&1
exit $LASTEXITCODE
