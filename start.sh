#!/bin/bash
# ==============================================================================
# JobTrace — Single Full Stack Startup Script (Bash)
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
echo "                  JobTrace — Full Stack Application                     "
echo "========================================================================"
echo ""
echo "  [Frontend Dashboard]"
echo "    ➜  Local:    http://localhost:$FRONTEND_PORT"
echo "    ➜  Network:  http://${NETWORK_IP}:$FRONTEND_PORT"
echo ""
echo "  [Backend API & Radar Engine]"
echo "    ➜  Local:    http://127.0.0.1:$BACKEND_PORT"
echo "    ➜  Network:  http://${NETWORK_IP}:$BACKEND_PORT"
echo "    ➜  Swagger:  http://127.0.0.1:$BACKEND_PORT/docs"
echo ""
echo "========================================================================"
echo "  Press Ctrl+C at any time to stop both servers."
echo "========================================================================"
echo ""

BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

# 3. Check Python
PYTHON_BIN="python3"
if [ -x "$ROOT_DIR/.venv/bin/python3" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python3"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
elif ! command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python"
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

sleep 1

# 7. Start Frontend in foreground
(cd "$FRONTEND_DIR" && npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT")
