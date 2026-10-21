# ==============================================================================
# JobTrace - Backend API Server Starter (PowerShell)
# Starts FastAPI server on http://127.0.0.1:8000
# ==============================================================================
param(
    [int]$Port = 8000
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Ensure python can locate backend packages
$env:PYTHONPATH = $ScriptDir + ';' + $env:PYTHONPATH

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  JobTrace - Starting Backend API Server                  " -ForegroundColor Green
Write-Host "  URL:          http://127.0.0.1:$Port                    " -ForegroundColor Yellow
Write-Host "  Swagger Docs: http://127.0.0.1:$Port/docs               " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -m jobtrace.main web --port $Port
} else {
    python -m jobtrace.main web --port $Port
}
