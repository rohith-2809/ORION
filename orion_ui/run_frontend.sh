#!/bin/bash
echo "[ORION] Starting Frontend via Linux NPM..."

# Ensure we are in the right directory
cd ~/ORION/orion || exit

# Force use of Linux npm
NPM_EXEC="/usr/bin/npm"

if [ ! -f "$NPM_EXEC" ]; then
    echo "Error: Linux npm not found at $NPM_EXEC"
    echo "Please ensure you installed it via: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs"
    exit 1
fi

# Clean if requested
if [ "$1" == "clean" ]; then
    echo "[ORION] Cleaning node_modules..."
    rm -rf node_modules package-lock.json
    echo "[ORION] Installing dependencies..."
    $NPM_EXEC install
fi

# Run Dev Server
echo "[ORION] Launching Vite..."
$NPM_EXEC run dev -- --host
