"""
Chat Session Constants
======================

Shared constants for all chat session types (assistant, spec, expand).

The canonical ``API_ENV_VARS`` list lives in ``env_constants.py`` at the
project root and is re-exported here for convenience so that existing
imports (``from .chat_constants import API_ENV_VARS``) continue to work.
"""

import logging
import sys
from pathlib import Path
from typing import Any, AsyncGenerator

# -------------------------------------------------------------------
# Root directory of the autoforge project (repository root).
# Used throughout the server package whenever the repo root is needed.
# -------------------------------------------------------------------
ROOT_DIR = Path(__file__).parent.parent.parent

# Ensure the project root is on sys.path so we can import env_constants
# from the root-level module without requiring a package install.
_root_str = str(ROOT_DIR)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)

# -------------------------------------------------------------------
# Environment variables forwarded to Claude CLI subprocesses.
# Single source of truth lives in env_constants.py at the project root.
# Re-exported here so existing ``from .chat_constants import API_ENV_VARS``
# imports continue to work unchanged.
# -------------------------------------------------------------------
from env_constants import API_ENV_VARS  # noqa: E402, F401
from rate_limit_utils import is_rate_limit_error, parse_retry_after  # noqa: E402, F401

from ..schemas import FileAttachment
from ..utils.document_extraction import (
    extract_text_from_document,
    is_document,
    is_image,
)

logger = logging.getLogger(__name__)


def check_rate_limit_error(exc: Exception) -> tuple[bool, int | None]:
    """Inspect an exception and determine if it represents a rate-limit.

    Returns ``(is_rate_limit, retry_seconds)``.  ``retry_seconds`` is the
    parsed Retry-After value when available, otherwise ``None`` (caller
    should use exponential backoff).
    """
    # MessageParseError = unknown CLI message type (e.g. "rate_limit_event").
    # These are informational events, NOT actual rate limit errors.
    # The word "rate_limit" in the type name would false-positive the regex.
    if type(exc).__name__ == "MessageParseError":
        return False, None

    # For all other exceptions: match error text against known rate-limit patterns
    exc_str = str(exc)
    if is_rate_limit_error(exc_str):
        retry = parse_retry_after(exc_str)
        return True, retry

    return False, None


def format_client_init_error(exc: Exception) -> str:
    """Build an actionable error message for Claude client startup failures.

    The Claude Agent SDK raises an opaque ``Control request timeout:
    initialize`` when the Claude CLI subprocess never completes the
    initialize handshake (auth problems, broken/missing CLI, PATH issues,
    unsupported Python, antivirus interference, slow machines).  Translate
    that into concrete guidance instead of surfacing the raw error.
    """
    if "Control request timeout" in str(exc):
        msg = (
            "Claude client timed out during startup (the Claude CLI did not "
            "respond to the initialize handshake). Common causes:\n"
            "- Claude CLI not authenticated: run `claude login` or set ANTHROPIC_API_KEY\n"
            "- Claude CLI not installed or outdated: run `npm install -g @anthropic-ai/claude-code`\n"
            "- Antivirus/firewall blocking the CLI subprocess (common on Windows)\n"
            "- Slow machine: raise the timeout by setting the environment variable "
            "CLAUDE_CODE_STREAM_CLOSE_TIMEOUT=120000 before starting AutoForge"
        )
        if sys.version_info < (3, 11):
            py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
            msg = (
                f"You are running Python {py}, but AutoForge requires Python 3.11+. "
                "Recreate your virtual environment with Python 3.11+ and try again.\n\n" + msg
            )
        return msg
    return f"Failed to initialize Claude: {exc}"


async def safe_receive_response(client: Any, log: logging.Logger) -> AsyncGenerator:
    """Wrap ``client.receive_response()`` to skip ``MessageParseError``.

    The Claude Code CLI may emit message types (e.g. ``rate_limit_event``)
    that the installed Python SDK does not recognise, causing
    ``MessageParseError`` which kills the async generator.  The CLI
    subprocess is still alive and the SDK uses a buffered memory channel,
    so we restart ``receive_response()`` to continue reading remaining
    messages without losing data.
    """
    max_retries = 50
    retries = 0
    while True:
        try:
            async for msg in client.receive_response():
                yield msg
            return  # Normal completion
        except Exception as exc:
            if type(exc).__name__ == "MessageParseError":
                retries += 1
                if retries > max_retries:
                    log.error(f"Too many unrecognized CLI messages ({retries}), stopping")
                    return
                log.warning(f"Ignoring unrecognized message from Claude CLI: {exc}")
                continue
            raise


def build_attachment_content_blocks(attachments: list[FileAttachment]) -> list[dict]:
    """Convert FileAttachment objects to Claude API content blocks.

    Images become image content blocks (passed directly to Claude's vision).
    Documents are extracted to text and become text content blocks.

    Raises:
        DocumentExtractionError: If a document cannot be read.
    """
    blocks: list[dict] = []
    for att in attachments:
        if is_image(att.mimeType):
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": att.mimeType,
                    "data": att.base64Data,
                }
            })
        elif is_document(att.mimeType):
            text = extract_text_from_document(att.base64Data, att.mimeType, att.filename)
            blocks.append({
                "type": "text",
                "text": f"[Content of uploaded file: {att.filename}]\n\n{text}",
            })
    return blocks


async def make_multimodal_message(content_blocks: list[dict]) -> AsyncGenerator[dict, None]:
    """Yield a single multimodal user message in Claude Agent SDK format.

    The Claude Agent SDK's ``query()`` method accepts either a plain string
    or an ``AsyncIterable[dict]`` for custom message formats.  This helper
    wraps a list of content blocks (text and/or images) in the expected
    envelope.

    Args:
        content_blocks: List of content-block dicts, e.g.
            ``[{"type": "text", "text": "..."}, {"type": "image", ...}]``.

    Yields:
        A single dict representing the user message.
    """
    yield {
        "type": "user",
        "message": {"role": "user", "content": content_blocks},
        "parent_tool_use_id": None,
        "session_id": "default",
    }
