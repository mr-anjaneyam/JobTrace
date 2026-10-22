# ==============================================================================
# JobTrace - Stop All Running Services Script (PowerShell)
# Frees ports 3000 & 8000 and kills any orphan backend/frontend processes
# ==============================================================================

Write-Host ''
Write-Host '========================================================' -ForegroundColor Cyan
Write-Host '  JobTrace - Stopping All Running Services              ' -ForegroundColor Yellow
Write-Host '========================================================' -ForegroundColor Cyan

# 1. Free ports 3000 and 8000
$targetPorts = @(3000, 8000)
foreach ($port in $targetPorts) {
    try {
        $connections = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        foreach ($conn in $connections) {
            $pidToKill = $conn.OwningProcess
            if ($pidToKill -and $pidToKill -gt 4) {
                Write-Host ('  Stopping process on port ' + $port + ' (PID: ' + $pidToKill + ')...') -ForegroundColor DarkYellow
                Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        # Fallback to netstat if Get-NetTCPConnection fails
        try {
            $netstatLines = netstat -ano | Select-String (':' + $port + '\s')
            foreach ($line in $netstatLines) {
                $tokens = ($line.ToString().Trim() -split '\s+')
                $netPid = $tokens[-1]
                if ($netPid -match '^\d+$' -and [int]$netPid -gt 4) {
                    Write-Host ('  Stopping process on port ' + $port + ' (PID: ' + $netPid + ')...') -ForegroundColor DarkYellow
                    Stop-Process -Id [int]$netPid -Force -ErrorAction SilentlyContinue
                }
            }
        } catch { }
    }
}

# 2. Terminate any lingering python / node processes related to jobtrace / vite
try {
    $processes = Get-Process -Name 'python', 'py', 'node' -ErrorAction SilentlyContinue
    foreach ($proc in $processes) {
        try {
            # Check command line if accessible
            $wmi = Get-CimInstance Win32_Process -Filter ("ProcessId = " + $proc.Id) -ErrorAction SilentlyContinue
            $cmd = if ($wmi -and $wmi.CommandLine) { $wmi.CommandLine } else { '' }
            if ($cmd -match 'jobtrace' -or $cmd -match 'vite') {
                Write-Host ('  Terminating orphan process: ' + $proc.ProcessName + ' (PID: ' + $proc.Id + ')...') -ForegroundColor DarkYellow
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
        } catch { }
    }
} catch { }

Write-Host ''
Write-Host '  All services stopped. Ports 3000 and 8000 are clean.' -ForegroundColor Green
Write-Host '========================================================' -ForegroundColor Cyan
Write-Host ''
