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

PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1 \
        && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PY="$candidate"
        break
    fi
done
if [ -z "$PY" ]; then
    echo "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/"
    exit 1
fi

DEP_CHECK="import importlib.util as u, sys; need = ('fastapi', 'uvicorn', 'yaml', 'requests'); sys.exit(0 if all(u.find_spec(m) for m in need) and (u.find_spec('python_multipart') or u.find_spec('multipart')) else 1)"
if ! "$PY" -c "$DEP_CHECK" 2>/dev/null; then
    echo "Installing backend dependencies first..."
    "$PY" -m pip install -r requirements.txt || exit 1
fi

exec "$PY" -m jobtrace.main web --port "$PORT"
