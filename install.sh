#!/bin/bash
# One-shot setup: venv, deps, and launchd jobs for JobTrace.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "==> creating virtualenv"
python3 -m venv .venv
./.venv/bin/pip -q install -r requirements.txt

[ -f config.yaml ] || { cp config.example.yaml config.yaml; echo "==> created config.yaml — edit it"; }

if [ "$(uname)" = "Darwin" ]; then
  echo "==> installing macOS schedules"
  mkdir -p ~/Library/LaunchAgents
  for job in com.jobtrace.weekly com.jobtrace.daily; do
    sed "s|__DIR__|$DIR|g" "$job.plist" > ~/Library/LaunchAgents/"$job.plist"
    launchctl unload ~/Library/LaunchAgents/"$job.plist" 2>/dev/null || true
    launchctl load  ~/Library/LaunchAgents/"$job.plist"
    echo "    $job"
  done
  echo "    weekly digest  Mondays 09:00"
  echo "    daily alerts   every day 09:30 (watched companies only)"
fi

cat <<'MSG'

Done. Three things left to get started:
  1. Put your resume in this folder and point resume_path at it in config.yaml
  2. Configure your Telegram Bot Token & Chat ID in config.yaml (or run.sh)
  3. Verify Telegram notifications:   ./run.example.sh test

MSG
