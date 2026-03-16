"""
Authentication Error Detection
==============================

Shared utilities for detecting Claude CLI authentication errors.
Used by both CLI (start.py) and server (process_manager.py) to provide
consistent error detection and messaging.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

# Patterns that indicate authentication errors from Claude CLI
AUTH_ERROR_PATTERNS = [
    r"not\s+logged\s+in",
    r"not\s+authenticated",
    r"authentication\s+(failed|required|error)",
    r"login\s+required",
    r"please\s+(run\s+)?['\"]?claude\s+login",
    r"unauthorized",
    r"invalid\s+(token|credential|api.?key)",
    r"expired\s+(token|session|credential)",
    r"could\s+not\s+authenticate",
    r"sign\s+in\s+(to|required)",
]


def is_auth_error(text: str) -> bool:
    """
    Check if text contains Claude CLI authentication error messages.

    Uses case-insensitive pattern matching against known error messages.

    Args:
        text: Output text to check

    Returns:
        True if any auth error pattern matches, False otherwise
    """
    if not text:
        return False
    text_lower = text.lower()
    for pattern in AUTH_ERROR_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


# CLI-style help message (for terminal output)
AUTH_ERROR_HELP_CLI = """
==================================================
  Authentication Error Detected
==================================================

Claude CLI requires authentication to work.

To fix this, run:
  claude login

This will open a browser window to sign in.
After logging in, try running this command again.
==================================================
"""

# Server-style help message (for WebSocket streaming)
AUTH_ERROR_HELP_SERVER = """
================================================================================
  AUTHENTICATION ERROR DETECTED
================================================================================

Claude CLI requires authentication to work.

To fix this, run:
  claude login

This will open a browser window to sign in.
After logging in, try starting the agent again.
================================================================================
"""


def print_auth_error_help() -> None:
    """Print helpful message when authentication error is detected (CLI version)."""
    print(AUTH_ERROR_HELP_CLI)


def get_claude_auth_status() -> dict:
    """
    Get current Claude CLI authentication status.

    Uses 'claude auth status' command to check if user is logged in.
    Returns parsed JSON response or error information.

    Returns:
        Dict with authentication status. Keys include:
        - loggedIn: bool, whether user is authenticated
        - authMethod: str, authentication method (e.g., "claude.ai")
        - email: str or None, user email
        - subscriptionType: str or None, subscription level
        - error: str or None, error message if command failed
    """
    try:
        # Run claude auth status and capture JSON output
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10  # Prevent hanging
        )
        
        if result.returncode == 0:
            try:
                status_data = json.loads(result.stdout.strip())
                return status_data
            except json.JSONDecodeError as e:
                return {
                    "loggedIn": False,
                    "error": f"Failed to parse auth status: {e}",
                    "raw_output": result.stdout.strip()
                }
        else:
            # Command failed - likely not logged in or CLI not installed
            return {
                "loggedIn": False,
                "error": "Claude CLI authentication check failed",
                "stderr": result.stderr.strip() if result.stderr else None,
                "returncode": result.returncode
            }
            
    except subprocess.TimeoutExpired:
        return {
            "loggedIn": False,
            "error": "Authentication check timed out"
        }
    except FileNotFoundError:
        return {
            "loggedIn": False,
            "error": "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
        }
    except Exception as e:
        return {
            "loggedIn": False,
            "error": f"Unexpected error checking auth status: {e}"
        }


def is_logged_in() -> bool:
    """
    Check if user is currently logged in to Claude CLI.

    Returns:
        True if logged in, False otherwise
    """
    status = get_claude_auth_status()
    return status.get("loggedIn", False)


def check_login_and_report() -> bool:
    """
    Check login status and print helpful message if not logged in.

    Returns:
        True if logged in, False if not logged in
    """
    status = get_claude_auth_status()
    
    if not status.get("loggedIn", False):
        print("\n" + "=" * 60)
        print("  AUTHENTICATION REQUIRED")
        print("=" * 60)
        
        error = status.get("error")
        if error:
            print(f"Error: {error}")
        
        print("\nClaude CLI requires authentication to work.")
        print("To fix this, run:")
        print("  claude login")
        print("\nThis will open a browser window to sign in.")
        print("After logging in, try running this command again.")
        print("=" * 60)
        print()
        return False
    
    # User is logged in - optionally show status info
    email = status.get("email")
    subscription = status.get("subscriptionType")
    if email and subscription:
        print(f"[OK] Logged in as {email} ({subscription})")
    elif email:
        print(f"[OK] Logged in as {email}")
    else:
        print("[OK] Logged in to Claude CLI")
    
    return True
