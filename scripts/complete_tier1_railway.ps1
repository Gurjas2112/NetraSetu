# Finish Tier 1 after: Supabase migrated (.env.tier1), `railway login`, project linked.
# Project id: da130793-430e-410d-aef2-72521037b1dd (netrasetu_app_backend)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".env.tier1")) {
    throw "Run scripts/setup_tier1_supabase.py first."
}

railway whoami | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Run: railway login" }

railway link da130793-430e-410d-aef2-72521037b1dd

Write-Host "Deploy Keycloak (create a dedicated Railway service if prompted)..."
railway up --detach --dockerfile service/Dockerfile.keycloak
$kc = Read-Host "Paste the public Keycloak base URL (https://....up.railway.app, no trailing slash)"

$issuer = "$kc/realms/netrasetu"
(Get-Content .env.tier1) | ForEach-Object {
    if ($_ -match '^#\s*OIDC_ISSUER=') { "OIDC_ISSUER=$issuer" } else { $_ }
} | Set-Content .env.tier1 -Encoding utf8
if (-not (Select-String -Path .env.tier1 -Pattern '^OIDC_ISSUER=' -Quiet)) {
    Add-Content .env.tier1 "OIDC_ISSUER=$issuer"
}

Write-Host "Deploy gateway..."
railway up --detach --dockerfile service/Dockerfile.gateway
.\.venv\Scripts\python.exe scripts\railway_set_vars.py
$gw = Read-Host "Paste the public gateway URL (https://....up.railway.app)"

vercel env add VITE_API_BASE production --force --value $gw
vercel env add VITE_OIDC_ISSUER production --force --value $issuer
vercel --prod --yes

Write-Host "Laptop MATLAB worker (separate terminal):"
Write-Host "  matlab.engine.shareEngine('netrasetu')  % in MATLAB"
Write-Host "  powershell -File scripts/run_tier1_worker.ps1"
