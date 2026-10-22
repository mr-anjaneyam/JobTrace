#!/bin/bash
# One-shot setup for JobTrace: Python virtualenv, backend deps, frontend deps, config files.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "==> creating virtualenv"
python3 -m venv .venv
./.venv/bin/pip -q install -r requirements.txt

if command -v npm >/dev/null 2>&1; then
  echo "==> installing frontend dependencies"
  (cd frontend && npm install --no-audit --no-fund)
else
  echo "==> npm not found, skipping frontend install (install Node.js 18+ to use the web UI)"
fi

[ -f config.yaml ] || { cp config.example.yaml config.yaml; echo "==> created config.yaml, edit it"; }
[ -f .env ] || { cp .env.example .env; echo "==> created .env, add your Telegram and LLM keys"; }

cat <<'MSG'

Done. Next steps:
  1. Start the app:           ./start.sh
  2. Open the dashboard:      http://localhost:3000
  3. Upload your resume and add your Telegram bot token in the Settings dialog
  4. Verify Telegram:         cd backend && ../.venv/bin/python -m jobtrace.main test

MSG
