#!/bin/bash
# ==============================================================================
# JobTrace - Backend API Server Starter (Bash)
# Starts FastAPI server on http://127.0.0.1:8000
# ==============================================================================
cd "$(dirname "$0")" || exit 1
export PYTHONPATH=".:$PYTHONPATH"
PORT=${1:-8000}

echo "=========================================================="
echo "  JobTrace - Starting Backend API Server                  "
echo "  URL:          http://127.0.0.1:$PORT                    "
echo "  Swagger Docs: http://127.0.0.1:$PORT/docs               "
echo "=========================================================="

if command -v python3 &>/dev/null; then
    exec python3 -m jobtrace.main web --port "$PORT"
else
    exec python -m jobtrace.main web --port "$PORT"
fi
