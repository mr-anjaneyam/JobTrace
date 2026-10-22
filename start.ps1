# ==============================================================================
# JobTrace - Single Full Stack Startup Script (PowerShell)
# Starts Backend (FastAPI) and Frontend (React/Vite) concurrently with IP display
# ==============================================================================
param(
    [int]$FrontendPort = 3000,
    [int]$BackendPort = 8000
)

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RootDir

# 1. Detect Network IPv4 Address
$networkIp = $null
try {
    $networkIp = [System.Net.Dns]::GetHostAddresses([System.Net.Dns]::GetHostName()) |
        Where-Object {
            $_.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
            $_.IPAddressToString -notlike '127.*' -and
            $_.IPAddressToString -notlike '169.254.*'
        } |
        Select-Object -ExpandProperty IPAddressToString -First 1
} catch {
    $networkIp = $null
}

if (-not $networkIp) {
    try {
        $socket = New-Object System.Net.Sockets.Socket(
            [System.Net.Sockets.AddressFamily]::InterNetwork,
            [System.Net.Sockets.SocketType]::Dgram,
            [System.Net.Sockets.ProtocolType]::Udp
        )
        $socket.Connect('8.8.8.8', 65530)
        $networkIp = $socket.LocalEndPoint.Address.IPAddressToString
        $socket.Close()
    } catch {
        $networkIp = '127.0.0.1'
    }
}

# 2. Display Startup Banner
Write-Host ''
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host '                  JobTrace - Full Stack Application                     ' -ForegroundColor Green
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host '  [Frontend Dashboard]' -ForegroundColor White
Write-Host '    -> Local:    ' -NoNewline -ForegroundColor DarkGray
Write-Host ('http://localhost:' + $FrontendPort) -ForegroundColor Yellow
Write-Host '    -> Network:  ' -NoNewline -ForegroundColor DarkGray
Write-Host ('http://' + $networkIp + ':' + $FrontendPort) -ForegroundColor Green
Write-Host ''
Write-Host '  [Backend API Engine]' -ForegroundColor White
Write-Host '    -> Local:    ' -NoNewline -ForegroundColor DarkGray
Write-Host ('http://127.0.0.1:' + $BackendPort) -ForegroundColor Yellow
Write-Host '    -> Swagger:  ' -NoNewline -ForegroundColor DarkGray
Write-Host ('http://127.0.0.1:' + $BackendPort + '/docs') -ForegroundColor Cyan
Write-Host ''
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host '  Press Ctrl+C at any time to stop both servers.' -ForegroundColor DarkGray
Write-Host '========================================================================' -ForegroundColor Cyan
Write-Host ''

$backendDir = Join-Path $RootDir 'backend'
$frontendDir = Join-Path $RootDir 'frontend'

# 3. Check Python
$pyCmd = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }

# 4. Check Frontend dependencies
$reactModule = Join-Path $frontendDir 'node_modules\react'
if (-not (Test-Path $reactModule)) {
    Write-Host 'Installing frontend dependencies first...' -ForegroundColor Cyan
    Push-Location $frontendDir
    npm install
    Pop-Location
}

# 5. Start Backend Process in Background
$env:PYTHONPATH = $backendDir + ';' + $env:PYTHONPATH
$backendArgs = '-m jobtrace.main web --port ' + $BackendPort
$backendProcess = Start-Process -FilePath $pyCmd -ArgumentList $backendArgs -WorkingDirectory $backendDir -PassThru -NoNewWindow

Start-Sleep -Milliseconds 800

# 6. Run Frontend in Foreground
try {
    Push-Location $frontendDir
    npm run dev -- --host 0.0.0.0 --port $FrontendPort
}
finally {
    Pop-Location
    Write-Host ''
    if ($backendProcess) {
        Write-Host ('Stopping backend server (Process ID: ' + $backendProcess.Id + ')...') -ForegroundColor Yellow
        if (-not $backendProcess.HasExited) {
            Stop-Process -Id $backendProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
    Get-Process -Name 'python', 'py', 'node' -ErrorAction SilentlyContinue | Where-Object {
        $_.Id -eq $backendProcess.Id
    } | Stop-Process -Force -ErrorAction SilentlyContinue

    Write-Host 'Stopped all JobTrace services cleanly.' -ForegroundColor Green
}
