#!/bin/bash
#
# Install git hooks for autocoder
#
# Run this script to set up:
# - Auto version bumping on commits
# - Ruff linting fixes
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing git hooks..."

# Create pre-commit hook
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
#
# Pre-commit hook to auto-increment version
#

REPO_ROOT="$(git rev-parse --show-toplevel)"

# Bump version
echo "Bumping version..."
python3 "$REPO_ROOT/scripts/bump_version.py"
if [ $? -ne 0 ]; then
    echo "Warning: Version bump failed, continuing anyway"
fi

# Stage the updated VERSION.json
git add "$REPO_ROOT/VERSION.json" 2>/dev/null || true

# Run ruff if available
if command -v ruff &> /dev/null; then
    echo "Running ruff check..."
    ruff check "$REPO_ROOT" --fix 2>/dev/null || true
    git add -u 2>/dev/null || true
fi

exit 0
EOF

chmod +x "$HOOKS_DIR/pre-commit"

echo "Git hooks installed successfully!"
echo "  - pre-commit: Auto version bump + ruff linting"
