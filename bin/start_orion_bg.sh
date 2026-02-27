#!/bin/bash
# start_orion_bg.sh
# ---------------------------------------------------------
# ORION Headless Background Launcher
# Starts the ORION backend and frontend APIs silently.
# ---------------------------------------------------------

echo "[ORION] Initializing Headless Boot Sequence..."

# Resolve absolute path to script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# 1. Activate Environment (if applicable, adjust path as needed)
if [ -d "$DIR/ORION-env" ]; then
    source "$DIR/ORION-env/bin/activate"
fi

# 2. Kill existing Orion instances to prevent port conflicts
echo "[ORION] Terminating existing instances..."
pkill -f "python3 server.py"
pkill -f "npm run dev"
pkill -f vite

# 3. Start Backend Silently
echo "[ORION] Booting Cognitive Core (Backend) in background..."
cd "$DIR/../src/main"
nohup python3 server.py > ../../logs/orion_backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to initialize Socket.IO
sleep 5

# 4. Start Frontend Silently
echo "[ORION] Booting Interface (Frontend) in background..."
cd "$DIR/../orion_ui"
nohup npm run dev > ../logs/orion_frontend.log 2>&1 &
FRONTEND_PID=$!

cd "$DIR"

echo "======================================================"
echo "🌟 ORION IS ONLINE (Headless Mode)"
echo "Backend PID: $BACKEND_PID"
echo "Frontend PID: $FRONTEND_PID"
echo "Logs: tail -f orion_backend.log | tail -f orion_frontend.log"
echo "Interface available at: http://localhost:5173"
echo "======================================================"
echo "To stop ORION later, simply run: pkill -f \"python3 server.py\" && pkill -f \"npm run dev\""
