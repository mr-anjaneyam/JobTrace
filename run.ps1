# JobTrace - Runner script for Windows PowerShell
param (
    [string]$Command = "run",
    [switch]$DryRun
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Ensure backend package is in PYTHONPATH
$env:PYTHONPATH = "$ScriptDir\backend;$env:PYTHONPATH"

# Optional: set environment variables if not defined in config.yaml
# $env:TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
# $env:TELEGRAM_CHAT_ID = "your-telegram-chat-id"

$argsList = @("-m", "jobtrace.main", $Command)
if ($DryRun) {
    $argsList += "--dry-run"
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    py $argsList
} else {
    python $argsList
}
