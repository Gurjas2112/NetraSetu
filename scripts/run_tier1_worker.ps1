# Pull queue jobs from Supabase and grade with the shared MATLAB engine on this laptop.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Test-Path ".env.tier1")) { throw "Missing .env.tier1" }
Get-Content .env.tier1 | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}
$workerPass = $env:WORKER_DB_PASSWORD
if (-not $workerPass) { throw "WORKER_DB_PASSWORD missing in .env.tier1" }
$ref = "imlojjdueuesjwznuzez"
$pool = "aws-0-ap-south-1.pooler.supabase.com"
$enc = [uri]::EscapeDataString($workerPass)
$env:DATABASE_URL = "postgresql://worker.${ref}:${enc}@${pool}:5432/postgres?sslmode=require"
$env:GATEWAY_ENGINE = "matlab"
$env:MATLAB_SHARED_ENGINE = "netrasetu"
$env:WORKER_ID = "laptop-1"
.\.venv\Scripts\python.exe -m service.worker
