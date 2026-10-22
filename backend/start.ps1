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

$pyCmd = $null
foreach ($candidate in 'py', 'python', 'python3') {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" 2>$null
        if ($LASTEXITCODE -eq 0) { $pyCmd = $candidate; break }
    }
}
if (-not $pyCmd) {
    Write-Host 'Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/' -ForegroundColor Red
    exit 1
}

$depCheck = "import importlib.util as u, sys; need = ('fastapi', 'uvicorn', 'yaml', 'requests'); sys.exit(0 if all(u.find_spec(m) for m in need) and (u.find_spec('python_multipart') or u.find_spec('multipart')) else 1)"
& $pyCmd -c $depCheck 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Installing backend dependencies first...' -ForegroundColor Cyan
    & $pyCmd -m pip install -r (Join-Path $ScriptDir 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

& $pyCmd -m jobtrace.main web --port $Port
