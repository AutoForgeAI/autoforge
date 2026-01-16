#!/bin/bash
# AutoCoder UI Launcher for Unix/Linux/macOS

# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo ""
echo "===================================="
echo "  AutoCoder - Web UI"
echo "===================================="
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
