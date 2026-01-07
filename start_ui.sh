#!/bin/bash
cd "$(dirname "$0")"
# AutoCoder UI Launcher for Unix/Linux/macOS
# This script launches the web UI for the autonomous coding agent.

echo ""
echo "===================================="
echo "  AutoCoder UI"
echo "===================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python not found"
        echo "Please install Python from https://python.org"
        exit 1
    fi
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

# Run the Python launcher
python start_ui.py "$@"
