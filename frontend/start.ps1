# ==============================================================================
# JobTrace - Frontend Dev Server Starter (PowerShell)
# Starts Vite dev server on http://localhost:3000
# ==============================================================================
param(
    [int]$Port = 3000
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  JobTrace - Starting Frontend Dev Server                 " -ForegroundColor Green
Write-Host "  URL: http://localhost:$Port                             " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

$backendConn = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if (-not $backendConn) {
    Write-Host ""
    Write-Host "  [Notice] Backend API is not running on http://127.0.0.1:8000" -ForegroundColor DarkYellow
    Write-Host "  To run both servers together, use root: ..\start.ps1" -ForegroundColor Yellow
    Write-Host "  Or start backend in a separate terminal: cd ..\backend; .\start.ps1" -ForegroundColor DarkGray
    Write-Host ""
}

if (-not (Test-Path "node_modules/react")) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    npm install
}

npm run dev -- --port $Port
