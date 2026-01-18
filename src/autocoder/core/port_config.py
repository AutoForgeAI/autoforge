"""
Port Configuration
==================

AutoCoder needs *two* distinct kinds of port configuration:

1) **UI server port** (FastAPI) for the AutoCoder dashboard/API.
2) **Target app ports** (per-agent) for the application being built/tested.

Environment Variables:
- AUTOCODER_UI_PORT: AutoCoder UI server port (default: 8888)
- AUTOCODER_UI_HOST: AutoCoder UI bind host (default: 127.0.0.1)
- AUTOCODER_UI_ALLOW_REMOTE: Allow LAN access + relaxed CORS (default: false)
- AUTOCODER_API_PORT: Target app backend API port (default: 5000)
- AUTOCODER_WEB_PORT: Target app frontend dev server port (default: 5173)

Notes:
- Parallel mode allocates unique `AUTOCODER_API_PORT` / `AUTOCODER_WEB_PORT` per agent to avoid collisions.
- The UI port should be configured independently via `AUTOCODER_UI_PORT`.
"""

import os
import logging
from typing import Final

logger = logging.getLogger(__name__)

# Default ports
DEFAULT_UI_PORT: Final[int] = 8888
DEFAULT_APP_API_PORT: Final[int] = 5000
DEFAULT_APP_WEB_PORT: Final[int] = 5173


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _get_port(env_var: str, default: int) -> int:
    """
    Get a port number from an environment variable with fallback to default.

    Args:
        env_var: Environment variable name
        default: Default port if env var not set or invalid

    Returns:
        Port number as integer
    """
    try:
        port_str = os.environ.get(env_var, "")
        if port_str:
            port = int(port_str)
            # Validate port range (1-65535, avoid well-known ports 1-1023)
            if 1024 <= port <= 65535:
                return port
            else:
                logger.warning(
                    "%s=%s is out of valid range (1024-65535); using default %s",
                    env_var,
                    port,
                    default,
                )
    except ValueError:
        logger.warning("Invalid %s value; using default %s", env_var, default)

    return default


def get_api_port() -> int:
    """Get the target app backend API port from AUTOCODER_API_PORT (default: 5000)."""
    return _get_port("AUTOCODER_API_PORT", DEFAULT_APP_API_PORT)


def get_web_port() -> int:
    """Get the target app frontend dev server port from AUTOCODER_WEB_PORT (default: 5173)."""
    return _get_port("AUTOCODER_WEB_PORT", DEFAULT_APP_WEB_PORT)


def get_vite_port() -> int:
    """
    Back-compat helper.

    Historically, some parts of the codebase referred to the frontend dev server as "vite".
    For clarity, `AUTOCODER_WEB_PORT` now represents the frontend dev server port directly.
    """
    return get_web_port()


def get_ui_port() -> int:
    """Get the AutoCoder UI server port from AUTOCODER_UI_PORT (default: 8888)."""
    return _get_port("AUTOCODER_UI_PORT", DEFAULT_UI_PORT)


def get_ui_host() -> str:
    """Get the AutoCoder UI bind host from AUTOCODER_UI_HOST (default: 127.0.0.1)."""
    host = (os.environ.get("AUTOCODER_UI_HOST") or "").strip()
    return host or "127.0.0.1"


def get_ui_allow_remote() -> bool:
    """Return True if the UI should allow remote (LAN) access."""
    return _truthy_env("AUTOCODER_UI_ALLOW_REMOTE")


def get_api_base_url(host: str = "localhost") -> str:
    """
    Get the base URL for the backend API server.

    Args:
        host: Hostname or IP address (default: "localhost")

    Returns:
        Base URL as string (e.g., "http://localhost:8888")
    """
    return f"http://{host}:{get_api_port()}"


def get_web_base_url(host: str = "localhost") -> str:
    """
    Get the base URL for the frontend development server.

    Args:
        host: Hostname or IP address (default: "localhost")

    Returns:
        Base URL as string (e.g., "http://localhost:3000")
    """
    return f"http://{host}:{get_web_port()}"


def get_vite_base_url(host: str = "localhost") -> str:
    """
    Get the base URL for the Vite dev server.

    Args:
        host: Hostname or IP address (default: "localhost")

    Returns:
        Base URL as string (e.g., "http://localhost:5173")
    """
    return f"http://{host}:{get_vite_port()}"


def get_ui_cors_origins() -> list[str]:
    """
    Get list of allowed CORS origins based on configured ports.

    Returns:
        List of origin URLs for CORS configuration
    """
    if get_ui_allow_remote():
        raw = (os.environ.get("AUTOCODER_UI_ALLOWED_ORIGINS") or "").strip()
        if raw:
            parts = [p.strip() for p in raw.replace(";", ",").split(",") if p.strip()]
            return parts if parts else ["*"]
        return ["*"]

    ui_port = get_ui_port()

    # UI frontend is typically served via Vite in dev (default 5173) and can auto-increment.
    # Keep a small allowlist of common local ports rather than allowing arbitrary origins.
    ui_dev_ports = [5173, 5174, 5175, 5176]

    origins = [
        f"http://localhost:{ui_port}",
        f"http://127.0.0.1:{ui_port}",
    ]

    for p in ui_dev_ports:
        origins.append(f"http://localhost:{p}")
        origins.append(f"http://127.0.0.1:{p}")

    return origins


def get_browser_navigation_url() -> str:
    """
    Get the URL that agents should navigate to when testing the application.

    This is typically the frontend development server URL.

    Returns:
        URL as string (e.g., "http://localhost:3000")
    """
    return get_web_base_url()


def set_port_environment(api_port: int | None = None, web_port: int | None = None) -> None:
    """
    Set port environment variables for the current process.

    Useful for testing or when ports need to be programmatically configured.

    Args:
        api_port: Backend API port (optional)
        web_port: Frontend web port (optional)
    """
    if api_port is not None:
        os.environ["AUTOCODER_API_PORT"] = str(api_port)
    if web_port is not None:
        os.environ["AUTOCODER_WEB_PORT"] = str(web_port)
