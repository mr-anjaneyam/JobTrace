#!/bin/bash
# ==============================================================================
# JobTrace: Single Full Stack Startup Script (Bash)
# Starts Backend (FastAPI) and Frontend (React/Vite) concurrently with IP display
# ==============================================================================
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ -d "$ROOT_DIR/.venv/bin" ]; then
    export PATH="$ROOT_DIR/.venv/bin:$PATH"
fi

FRONTEND_PORT="${1:-3000}"
BACKEND_PORT="${2:-8000}"

# 1. Detect Network IP
NETWORK_IP=""
if command -v hostname >/dev/null 2>&1 && hostname -I >/dev/null 2>&1; then
    NETWORK_IP=$(hostname -I | awk '{print $1}')
elif command -v ip >/dev/null 2>&1; then
    NETWORK_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
elif command -v ifconfig >/dev/null 2>&1; then
    NETWORK_IP=$(ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1)
fi

[ -z "$NETWORK_IP" ] && NETWORK_IP="127.0.0.1"

# 2. Display Startup Banner
echo ""
echo "========================================================================"
echo "                  JobTrace: Full Stack Application                     "
echo "========================================================================"
echo ""
echo "  [Frontend Dashboard]"
echo "    ➜  Local:    http://localhost:$FRONTEND_PORT"
echo "    ➜  Network:  http://${NETWORK_IP}:$FRONTEND_PORT"
echo ""
echo "  [Backend API & JobTrace Engine]"
echo "    ➜  Local:    http://127.0.0.1:$BACKEND_PORT"
echo "    ➜  Swagger:  http://127.0.0.1:$BACKEND_PORT/docs"
echo ""
echo "========================================================================"
echo "  Press Ctrl+C at any time to stop both servers."
echo "========================================================================"
echo ""

BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# 3. Check Python (3.10+) and backend dependencies
PYTHON_BIN=""
for candidate in "$ROOT_DIR/.venv/bin/python3" "$ROOT_DIR/.venv/bin/python" python3 python; do
    if { [ -x "$candidate" ] || command -v "$candidate" >/dev/null 2>&1; } \
        && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/ and run this script again."
    exit 1
fi

DEP_CHECK="import importlib.util as u, sys; need = ('fastapi', 'uvicorn', 'yaml', 'requests'); sys.exit(0 if all(u.find_spec(m) for m in need) and (u.find_spec('python_multipart') or u.find_spec('multipart')) else 1)"
if ! "$PYTHON_BIN" -c "$DEP_CHECK" 2>/dev/null; then
    echo "Installing backend dependencies first..."
    "$PYTHON_BIN" -m pip install -r "$BACKEND_DIR/requirements.txt" || {
        echo "Could not install backend dependencies. Run: pip install -r backend/requirements.txt"
        exit 1
    }
fi

# 4. Check Frontend dependencies
if [ ! -d "$FRONTEND_DIR/node_modules/react" ]; then
    echo "Installing frontend dependencies first..."
    (cd "$FRONTEND_DIR" && npm install)
fi

# 5. Trap for clean exit
cleanup() {
    echo ""
    echo "Stopping all JobTrace services..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 6. Start Backend in background
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"
(cd "$BACKEND_DIR" && $PYTHON_BIN -m jobtrace.main web --port "$BACKEND_PORT") &
BACKEND_PID=$!

sleep 1.5
if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "The backend failed to start (see the error above). The dashboard will not work until it is fixed."
fi

# 7. Start Frontend in foreground
(cd "$FRONTEND_DIR" && npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT")
