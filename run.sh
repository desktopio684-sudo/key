#!/bin/bash
# ─────────────────────────────────────────────────────────────────
# run.sh — Launcher for the On-Screen Keyboard app
#
# Usage:
#   ./run.sh
#
# This script activates the project's virtual environment
# and launches the application.
# ─────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

# Check venv exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Error: Virtual environment not found at $VENV_DIR"
    echo "Create it with: python3 -m venv --system-site-packages venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Activate venv and run
source "$VENV_DIR/bin/activate"
python3 "$SCRIPT_DIR/main.py" "$@"
