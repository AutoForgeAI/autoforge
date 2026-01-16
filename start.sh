#!/bin/bash
cd "$(dirname "$0")"

# Load .env file if it exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo ""
echo "========================================"
echo "  AutoCoder - Autonomous Coding Agent"
echo "========================================"
echo ""

# Run autocoder CLI
if ! command -v autocoder &> /dev/null; then
    echo "[ERROR] autocoder command not found"
    echo ""
    echo "Please install the package first:"
    echo "  pip install -e '.[dev]'"
    echo ""
    exit 1
fi

autocoder
