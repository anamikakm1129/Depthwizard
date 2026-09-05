#!/usr/bin/env bash
set -e

echo "=============================================================================="
echo "   DEPTHWIZARD SIH 2026 - POSIX LAUNCHER (macOS / Linux)"
echo "=============================================================================="

if [ -f "venv/bin/python" ]; then
    PY_EXE="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY_EXE="python3"
elif command -v python >/dev/null 2>&1; then
    PY_EXE="python"
else
    echo "[ERROR] Python 3 not found. Please install Python 3.10+ or set up venv."
    exit 1
fi

exec "$PY_EXE" scripts/run_app.py "$@"
