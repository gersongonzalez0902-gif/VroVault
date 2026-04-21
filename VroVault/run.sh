#!/usr/bin/env bash
# VroVault - Linux launcher
# Usage: bash run.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python 3.10+
PYTHON=$(command -v python3 || command -v python)
PY_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PY_VERSION"

# Install deps if venv not present
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

source .venv/bin/activate

echo "Installing/checking dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "Starting VroVault..."
python main.py
