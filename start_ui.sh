#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1
# AutoForge UI Launcher for Unix/Linux/macOS
# This script launches the web UI for the autonomous coding agent.
#
# Works with plain python3/pip3 installs as well as uv (https://docs.astral.sh/uv/).
# When uv is on PATH it is used to create the venv and install dependencies.

MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=11

echo ""
echo "===================================="
echo "  AutoForge UI"
echo "===================================="
echo ""

# Check if Claude CLI is installed
if ! command -v claude &> /dev/null; then
    echo "[!] Claude CLI not found"
    echo ""
    echo "    The agent requires Claude CLI to work."
    echo "    Install it from: https://claude.ai/download"
    echo ""
    echo "    After installing, set ANTHROPIC_API_KEY or run: claude login"
    echo ""
else
    echo "[OK] Claude CLI found"
    # Note: Claude CLI no longer stores credentials in ~/.claude/.credentials.json
    # We can't reliably check auth status without making an API call
    if [ -d "$HOME/.claude" ]; then
        echo "     (Set ANTHROPIC_API_KEY or run: claude login)"
    else
        echo "[!] Claude CLI not configured - set ANTHROPIC_API_KEY or run 'claude login'"
    fi
fi
echo ""

# Returns success if the given interpreter is Python >= MIN_PYTHON_MAJOR.MIN_PYTHON_MINOR
python_is_supported() {
    "$1" -c "import sys; sys.exit(0 if sys.version_info >= ($MIN_PYTHON_MAJOR, $MIN_PYTHON_MINOR) else 1)" &> /dev/null
}

# Find a suitable Python interpreter (newest first, then generic names)
PYTHON_CMD=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3 python; do
    if command -v "$candidate" &> /dev/null && python_is_supported "$candidate"; then
        PYTHON_CMD="$candidate"
        break
    fi
done

# Detect uv (optional, used for faster venv creation and installs)
USE_UV=0
if command -v uv &> /dev/null; then
    USE_UV=1
    echo "[OK] uv found - using it for Python package management"
fi

if [ -z "$PYTHON_CMD" ] && [ "$USE_UV" -eq 0 ]; then
    echo "[ERROR] Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ not found"
    for candidate in python3 python; do
        if command -v "$candidate" &> /dev/null; then
            echo "        Found $("$candidate" --version 2>&1) at $(command -v "$candidate"), which is too old."
            break
        fi
    done
    echo "Please install Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR or newer from https://python.org"
    echo "(or install uv: https://docs.astral.sh/uv/ - it can provide Python for you)"
    exit 1
fi
if [ -n "$PYTHON_CMD" ]; then
    echo "[OK] Using $("$PYTHON_CMD" --version 2>&1) ($PYTHON_CMD)"
fi

VENV_PYTHON="venv/bin/python"

# Check if venv exists with correct structure for this platform
# Windows venvs have Scripts/, Linux/macOS have bin/
RECREATE_VENV=0
if [ ! -f "venv/bin/activate" ]; then
    if [ -d "venv" ]; then
        echo "[INFO] Detected incompatible virtual environment (possibly created on Windows)"
        RECREATE_VENV=1
    fi
elif ! python_is_supported "$VENV_PYTHON"; then
    echo "[INFO] Existing virtual environment is broken or uses Python older than $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR"
    RECREATE_VENV=1
fi

if [ "$RECREATE_VENV" -eq 1 ]; then
    echo "[INFO] Recreating virtual environment..."
    rm -rf venv
    if [ -d "venv" ]; then
        echo "[ERROR] Failed to remove existing virtual environment"
        echo "Please manually delete the 'venv' directory and try again:"
        echo "  rm -rf venv"
        exit 1
    fi
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    if [ "$USE_UV" -eq 1 ]; then
        # --seed installs pip into the venv so start_ui.py can also manage packages
        if [ -n "$PYTHON_CMD" ]; then
            # Pass the absolute path: uv treats bare "python3"/"python" as a version
            # request and may pick one of its own (possibly older) managed Pythons
            uv venv venv --seed --python "$(command -v "$PYTHON_CMD")"
        else
            uv venv venv --seed --python ">=$MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR"
        fi
    else
        "$PYTHON_CMD" -m venv venv
    fi
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        if [ "$USE_UV" -eq 1 ]; then
            echo "Try: uv python install $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR"
        else
            echo "Please ensure the venv module is installed:"
            echo "  Ubuntu/Debian: sudo apt install python3-venv"
            echo "  Or try: $PYTHON_CMD -m ensurepip"
        fi
        exit 1
    fi
    if ! python_is_supported "$VENV_PYTHON"; then
        echo "[ERROR] The new virtual environment uses $("$VENV_PYTHON" --version 2>&1), but Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ is required"
        echo "Please install Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR or newer, then run: rm -rf venv && ./start_ui.sh"
        exit 1
    fi
fi

# Activate the virtual environment
source venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment"
    echo "The venv may be corrupted. Try: rm -rf venv && ./start_ui.sh"
    exit 1
fi

# Install dependencies (always through the venv's interpreter, never a bare pip/pip3)
echo "Installing dependencies..."
if [ "$USE_UV" -eq 1 ]; then
    uv pip install --python "$VENV_PYTHON" -r requirements.txt --quiet
else
    # venvs created without pip (e.g. by uv without --seed) need it bootstrapped
    if ! "$VENV_PYTHON" -m pip --version &> /dev/null; then
        "$VENV_PYTHON" -m ensurepip --upgrade &> /dev/null
    fi
    "$VENV_PYTHON" -m pip install -r requirements.txt --quiet
fi
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install Python dependencies"
    exit 1
fi

# Ensure playwright-cli is available for browser automation
if ! command -v playwright-cli &> /dev/null; then
    echo "Installing playwright-cli for browser automation..."
    npm install -g @playwright/cli --quiet 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Note: Could not install playwright-cli. Install manually: npm install -g @playwright/cli"
    fi
fi

# Run the Python launcher with the venv interpreter
"$VENV_PYTHON" start_ui.py "$@"
