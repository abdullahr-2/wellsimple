# One-click launcher for the WellSimple demo (Windows PowerShell).
#   .\run_demo.ps1 -DataDir "C:\path\to\Competition Dataset"
# Builds the scored tables and the A/B pilot the first time, then starts the app and opens the browser.
# The dataset is restricted: it is read from -DataDir and never copied into this repo.
param(
  [string]$DataDir = $env:DATA_DIR,
  [string]$WorkDir = (Join-Path $PSScriptRoot "artifacts"),
  [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
if (-not $DataDir -or -not (Test-Path (Join-Path $DataDir "daily_production.parquet"))) {
  Write-Host "Point -DataDir at the folder that contains daily_production.parquet, well_jobs.parquet and production_failures.parquet." -ForegroundColor Red
  Write-Host 'Example: .\run_demo.ps1 -DataDir "C:\Users\you\Competition Dataset"'
  exit 1
}
$env:DATA_DIR = $DataDir
$env:WORK_DIR = $WorkDir
Set-Location $PSScriptRoot
if (-not (Test-Path (Join-Path $WorkDir "wells.parquet"))) {
  Write-Host "First run: scoring wells (about 2 minutes)..."
  python scripts/build_artifacts.py
  if ($LASTEXITCODE -ne 0) { exit 1 }
}
if (-not (Test-Path (Join-Path $WorkDir "pilot.json"))) {
  Write-Host "Building the A/B pilot..."
  python scripts/build_pilot.py
  if ($LASTEXITCODE -ne 0) { exit 1 }
}
$url = "http://127.0.0.1:$Port/"
# open the browser once the server answers (loading takes about 30 seconds)
Start-Job -ArgumentList $url -ScriptBlock {
  param($u)
  for ($i = 0; $i -lt 90; $i++) { Start-Sleep 2; try { Invoke-WebRequest ($u + "api/crews") -UseBasicParsing -TimeoutSec 3 | Out-Null; Start-Process $u; break } catch {} }
} | Out-Null
Write-Host "Starting WellSimple at $url   (manager)   and   ${url}crew   (crew). Press Ctrl+C to stop."
python -m uvicorn wellsimple.server:load_app --factory --port $Port
