#!/bin/bash
# ==============================================================================
# JobTrace - Frontend Dev Server Starter (Bash)
# Starts Vite dev server on http://localhost:3000
# ==============================================================================
cd "$(dirname "$0")" || exit 1
PORT=${1:-3000}

echo "=========================================================="
echo "  JobTrace - Starting Frontend Dev Server                 "
echo "  URL: http://localhost:$PORT                             "
echo "=========================================================="

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

exec npm run dev -- --port "$PORT"
