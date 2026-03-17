#!/usr/bin/env bash
# Start VTEX Integration Tools webapp
# Usage: ./webapp/start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=== VTEX Integration Tools ==="
echo ""

# ── Backend ──────────────────────────────────────────────────────
echo "→ Setting up backend…"
cd "$SCRIPT_DIR/backend"

if [ ! -d "venv" ]; then
  echo "  Creating backend virtualenv…"
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo "  Backend dependencies OK"

# Start backend in background
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "  Backend running on http://localhost:8000 (PID $BACKEND_PID)"

# ── Frontend ─────────────────────────────────────────────────────
echo ""
echo "→ Setting up frontend…"
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
  echo "  Installing npm dependencies…"
  npm install
fi

echo "  Starting frontend…"
npm run dev &
FRONTEND_PID=$!
echo "  Frontend running on http://localhost:5173 (PID $FRONTEND_PID)"

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo "=== App is running ==="
echo "  Open: http://localhost:5173"
echo ""
echo "  Backend API: http://localhost:8000"
echo "  Press Ctrl+C to stop"
echo ""

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM

wait
