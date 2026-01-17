#!/bin/bash
# AutoCoder UI Launcher for Unix/Linux/macOS

# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Activate venv if present
if [ -f ".venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
fi

echo ""
echo "  Starting AutoCoder Web UI..."
UI_PORT="${AUTOCODER_UI_PORT:-8888}"
echo "  Opening http://127.0.0.1:${UI_PORT}  (set AUTOCODER_OPEN_UI=0 to disable)"
echo ""

# Run autocoder-ui command
if ! command -v autocoder-ui &> /dev/null; then
    echo "[ERROR] autocoder-ui command not found"
    echo ""
    echo "Please install the package first:"
    echo "  pip install -e '.[dev]'"
    echo ""
    exit 1
fi

autocoder-ui
