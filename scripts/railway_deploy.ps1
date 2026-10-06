# Deploy netrasetu_app_backend on Railway (project da130793-430e-410d-aef2-72521037b1dd).
#
# Project deploy token (cannot run whoami/link):
#   Project -> netrasetu_app_backend -> Settings -> Tokens -> Generate (production)
#   $env:RAILWAY_TOKEN = '<token>'
#
# Full CLI (link, variables, whoami):
#   https://railway.app/account/tokens -> $env:RAILWAY_API_TOKEN = '<token>'
#
# Create two empty services: keycloak, gateway

param(
    [string]$ProjectId = "da130793-430e-410d-aef2-72521037b1dd",
    [string]$Environment = "production",
    [string]$KeycloakService = "keycloak",
    [string]$GatewayService = "gateway"
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

function Require-Railway {
    if ($env:RAILWAY_API_TOKEN -and $env:RAILWAY_TOKEN) {
        Write-Host "Both token env vars set; using RAILWAY_TOKEN (project) and clearing RAILWAY_API_TOKEN."
        Remove-Item Env:RAILWAY_API_TOKEN
    }
    if (-not $env:RAILWAY_TOKEN -and -not $env:RAILWAY_API_TOKEN) {
        Write-Host "Set RAILWAY_TOKEN (project) or RAILWAY_API_TOKEN (account)." -ForegroundColor Yellow
        exit 1
    }
    if ($env:RAILWAY_API_TOKEN) {
        railway whoami 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Invalid RAILWAY_API_TOKEN" }
    }
}

function Set-ServiceDockerfile([string]$Service, [string]$DockerfilePath) {
    $cmd = @("variables", "set", "RAILWAY_DOCKERFILE_PATH=$DockerfilePath", "-s", $Service, "-p", $ProjectId)
    railway @cmd | Out-Null
}

function Get-ServiceDomain([string]$Service) {
    $raw = railway domain -s $Service -p $ProjectId --json 2>&1 | Out-String
    if ($raw -match 'https://[^\s"]+\.up\.railway\.app') {
        return $Matches[0].TrimEnd('/')
    }
    return $null
}

Require-Railway
if (-not (Test-Path ".env.tier1")) { throw "Missing .env.tier1" }

if ($env:RAILWAY_API_TOKEN) {
    railway link $ProjectId --environment $Environment | Out-Null
}
$deployFlags = @("-d", "-p", $ProjectId, "-e", $Environment)

Write-Host "Configuring Keycloak ($KeycloakService)..."
Set-ServiceDockerfile $KeycloakService "service/Dockerfile.keycloak"
railway variables set "KC_BOOTSTRAP_ADMIN_USERNAME=admin" -s $KeycloakService -p $ProjectId | Out-Null
railway variables set "KC_BOOTSTRAP_ADMIN_PASSWORD=$([guid]::NewGuid().ToString('N'))" -s $KeycloakService -p $ProjectId | Out-Null

Write-Host "Deploying Keycloak..."
railway up @deployFlags -s $KeycloakService
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Start-Sleep -Seconds 8
$kcBase = Get-ServiceDomain $KeycloakService
if (-not $kcBase) {
    $kcBase = (Read-Host "Keycloak domain not ready — paste https://....up.railway.app").TrimEnd('/')
}
$issuer = "$kcBase/realms/netrasetu"
Write-Host "OIDC issuer: $issuer"

$envLines = Get-Content .env.tier1
$updated = @()
$hadIssuer = $false
foreach ($line in $envLines) {
    if ($line -match '^OIDC_ISSUER=' -or $line -match '^#\s*OIDC_ISSUER=') {
        $updated += "OIDC_ISSUER=$issuer"
        $hadIssuer = $true
    } else {
        $updated += $line
    }
}
if (-not $hadIssuer) { $updated += "OIDC_ISSUER=$issuer" }
$updated | Set-Content .env.tier1 -Encoding utf8

Write-Host "Configuring gateway ($GatewayService)..."
Set-ServiceDockerfile $GatewayService "service/Dockerfile.gateway"
$env:RAILWAY_SERVICE = $GatewayService
.\.venv\Scripts\python.exe scripts\railway_set_vars.py
Remove-Item Env:RAILWAY_SERVICE -ErrorAction SilentlyContinue

Write-Host "Deploying gateway..."
railway up @deployFlags -s $GatewayService
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Start-Sleep -Seconds 8
$gwBase = Get-ServiceDomain $GatewayService
if ($gwBase) {
    Write-Host "Gateway URL: $gwBase"
    if (Get-Command vercel -ErrorAction SilentlyContinue) {
        vercel env add VITE_API_BASE production --force --value $gwBase 2>$null
        vercel env add VITE_OIDC_ISSUER production --force --value $issuer 2>$null
        vercel --prod --yes 2>$null
        Write-Host "Vercel production redeploy triggered."
    }
} else {
    Write-Host "Run: railway domain -s $GatewayService  then update Vercel VITE_API_BASE"
}

Write-Host "Laptop grader: matlab.engine.shareEngine('netrasetu'); scripts/run_tier1_worker.ps1"
