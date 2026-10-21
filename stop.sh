#!/usr/bin/env bash
# ==============================================================================
# JobTrace - Stop All Running Services Script (Bash)
# ==============================================================================

echo ""
echo "Stopping all JobTrace services on ports 3000 & 8000..."

# Free port 3000
PIDS_3000=$(lsof -ti:3000 2>/dev/null || true)
if [ -n "$PIDS_3000" ]; then
    echo "  Killing processes on port 3000: $PIDS_3000"
    kill -9 $PIDS_3000 2>/dev/null || true
fi

# Free port 8000
PIDS_8000=$(lsof -ti:8000 2>/dev/null || true)
if [ -n "$PIDS_8000" ]; then
    echo "  Killing processes on port 8000: $PIDS_8000"
    kill -9 $PIDS_8000 2>/dev/null || true
fi

# Kill any lingering uvicorn or jobtrace processes
pkill -f "jobtrace.main web" 2>/dev/null || true

echo "All services stopped cleanly. Ports 3000 and 8000 are freed."
echo ""
