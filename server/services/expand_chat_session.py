"""
Expand Chat Session
===================

Manages interactive project expansion conversation with Claude.
Uses the expand-project.md skill to help users add features to existing projects.

In "onboard" mode it uses the onboard-project.md skill instead: Claude explores an
existing codebase that AutoForge has no spec for yet, writes app_spec.txt describing
it, records the existing functionality as passing features, and then plans new ones.
"""

import asyncio
import json
import logging
import os
import shutil
import sys
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Literal, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from claude_agent_sdk.types import HookMatcher
from dotenv import load_dotenv

from ..schemas import FileAttachment
from ..utils.document_extraction import DocumentExtractionError
from .chat_constants import (
    ROOT_DIR,
    build_attachment_content_blocks,
    check_rate_limit_error,
    format_client_init_error,
    make_multimodal_message,
    safe_receive_response,
)

# Load environment variables from .env file if present
load_dotenv()

logger = logging.getLogger(__name__)

# Feature MCP tools needed for expand session
EXPAND_FEATURE_TOOLS = [
    "mcp__features__feature_create",
    "mcp__features__feature_create_bulk",
    "mcp__features__feature_get_stats",
]

ExpandMode = Literal["expand", "onboard"]
EXPAND_MODES: tuple[ExpandMode, ...] = ("expand", "onboard")

SKILL_FILES: dict[ExpandMode, str] = {
    "expand": "expand-project.md",
    "onboard": "onboard-project.md",
}

# File-modifying tools. Expand mode denies them outright; onboard mode allows
# Write/Edit but only for app_spec.txt (enforced by a PreToolUse hook).
FILE_WRITE_TOOLS = ["Write", "Edit", "MultiEdit", "NotebookEdit"]

# Marker present in the unmodified app_spec template scaffolded for new projects
SPEC_TEMPLATE_MARKER = "YOUR_PROJECT_NAME"


def make_spec_only_write_hook(spec_path: Path):
    """
    Build a PreToolUse hook that blocks file writes to anything but spec_path.

    Onboarding needs to write app_spec.txt but must never touch the user's
    existing source code, so every write/edit outside that one file is blocked.
    """
    allowed = spec_path.resolve()

    async def spec_only_write_hook(input_data, tool_use_id=None, context=None):
        if input_data.get("tool_name") not in FILE_WRITE_TOOLS:
            return {}
        tool_input = input_data.get("tool_input", {}) or {}
        raw_path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        try:
            target = Path(raw_path)
            if not target.is_absolute():
                target = allowed.parent / target
            if raw_path and target.resolve() == allowed:
                return {}
        except (OSError, ValueError):
            pass
        return {
            "decision": "block",
            "reason": f"Onboarding may only write the app specification at {allowed}. "
                      "Existing source code must not be modified.",
        }

    return spec_only_write_hook


class ExpandChatSession:
    """
    Manages a project expansion conversation.

    Unlike SpecChatSession which writes spec files, this session:
    1. Reads existing app_spec.txt for context
    2. Chats with the user to define new features
    3. Claude creates features via the feature_create_bulk MCP tool

    In onboard mode there is no spec yet: Claude reads the codebase instead,
    writes app_spec.txt (the only file it may write), and records existing
    functionality as passing features before planning new ones.
    """

    def __init__(self, project_name: str, project_dir: Path, mode: ExpandMode = "expand"):
        """
        Initialize the session.

        Args:
            project_name: Name of the project being expanded
            project_dir: Absolute path to the project directory
            mode: "expand" to add features to a specced project, "onboard" to
                analyze an existing codebase that has no spec yet
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.mode: ExpandMode = mode
        self.client: Optional[ClaudeSDKClient] = None
        self.messages: list[dict] = []
        self.complete: bool = False
        self.created_at = datetime.now()
        self._conversation_id: Optional[str] = None
        self._client_entered: bool = False
        self.features_created: int = 0
        self.created_feature_ids: list[int] = []
        self._settings_file: Optional[Path] = None
        self._query_lock = asyncio.Lock()

    async def close(self) -> None:
        """Clean up resources and close the Claude client."""
        if self.client and self._client_entered:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception as e:
                logger.warning(f"Error closing Claude client: {e}")
            finally:
                self._client_entered = False
                self.client = None

        # Clean up temporary settings file
        if self._settings_file and self._settings_file.exists():
            try:
                self._settings_file.unlink()
            except Exception as e:
                logger.warning(f"Error removing settings file: {e}")

    async def start(self) -> AsyncGenerator[dict, None]:
        """
        Initialize session and get initial greeting from Claude.

        Yields message chunks as they stream in.
        """
        is_onboard = self.mode == "onboard"

        # Load the skill for this mode
        skill_path = ROOT_DIR / ".claude" / "commands" / SKILL_FILES[self.mode]

        if not skill_path.exists():
            yield {
                "type": "error",
                "content": f"{'Onboard' if is_onboard else 'Expand'} project skill not found at {skill_path}"
            }
            return

        from autoforge_paths import get_prompts_dir
        spec_path = get_prompts_dir(self.project_dir) / "app_spec.txt"
        if is_onboard:
            spec_path.parent.mkdir(parents=True, exist_ok=True)
            # Remove the unmodified scaffold template so Claude can write the spec
            # fresh (the SDK requires reading an existing file before overwriting it)
            if spec_path.exists():
                try:
                    if SPEC_TEMPLATE_MARKER in spec_path.read_text(encoding="utf-8", errors="replace"):
                        spec_path.unlink()
                        logger.info("Deleted scaffolded app_spec.txt template for onboarding")
                except OSError as e:
                    logger.warning(f"Could not inspect app_spec.txt template: {e}")
        elif not spec_path.exists():
            # Expand mode builds on the existing spec
            yield {
                "type": "error",
                "content": "Project has no app_spec.txt. Please create it first using spec creation."
            }
            return

        try:
            skill_content = skill_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            skill_content = skill_path.read_text(encoding="utf-8", errors="replace")

        # Find and validate Claude CLI before creating temp files
        system_cli = shutil.which("claude")
        if not system_cli:
            yield {
                "type": "error",
                "content": "Claude CLI not found. Please install it: npm install -g @anthropic-ai/claude-code"
            }
            return

        # Onboard mode may write app_spec.txt (and nothing else, see hook below)
        write_tools = ["Write", "Edit"] if is_onboard else []
        denied_tools = [t for t in FILE_WRITE_TOOLS if t not in write_tools] + ["Bash"]

        # Create temporary security settings file (unique per session to avoid conflicts)
        # Note: permission_mode="bypassPermissions" is safe here because:
        # 1. Bash (and in expand mode Write/Edit) is removed via disallowed_tools and the "deny" list
        # 2. In onboard mode a PreToolUse hook blocks writes to anything but app_spec.txt
        # 3. MCP tools are restricted to feature creation only
        # 4. No Bash access - cannot execute arbitrary commands
        security_settings = {
            "sandbox": {"enabled": True},
            "permissions": {
                "defaultMode": "bypassPermissions",
                "allow": [
                    "Read(./**)",
                    "Glob(./**)",
                    "Grep(./**)",
                    *EXPAND_FEATURE_TOOLS,
                ],
                "deny": denied_tools,
            },
        }
        from autoforge_paths import get_expand_settings_path
        settings_file = get_expand_settings_path(self.project_dir, uuid.uuid4().hex)
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        self._settings_file = settings_file
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(security_settings, f, indent=2)

        # Replace $ARGUMENTS with absolute project path
        project_path = str(self.project_dir.resolve())
        system_prompt = skill_content.replace("$ARGUMENTS", project_path)

        # Build environment overrides for API configuration
        from registry import DEFAULT_MODEL, get_effective_sdk_env, get_effort_setting
        sdk_env = get_effective_sdk_env()
        effort = get_effort_setting()

        # Determine model from SDK env (provider-aware) or fallback to env/default
        model = sdk_env.get("ANTHROPIC_DEFAULT_OPUS_MODEL") or os.getenv("ANTHROPIC_DEFAULT_OPUS_MODEL", DEFAULT_MODEL)

        # Build MCP servers config for feature creation
        mcp_servers = {
            "features": {
                "command": sys.executable,
                "args": ["-m", "mcp_server.feature_mcp"],
                "env": {
                    "PROJECT_DIR": str(self.project_dir.resolve()),
                    "PYTHONPATH": str(ROOT_DIR.resolve()),
                },
            },
        }

        # Create Claude SDK client
        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model=model,
                    effort=effort,  # type: ignore[arg-type]  # SDK 0.1.61 Literal omits "xhigh"
                    cli_path=system_cli,
                    system_prompt=system_prompt,
                    allowed_tools=[
                        "Read",
                        "Glob",
                        "Grep",
                        "WebFetch",
                        "WebSearch",
                        *write_tools,
                        *EXPAND_FEATURE_TOOLS,
                    ],
                    disallowed_tools=denied_tools,
                    mcp_servers=mcp_servers,  # type: ignore[arg-type]  # SDK accepts dict config at runtime
                    hooks={
                        "PreToolUse": [
                            HookMatcher(
                                matcher="|".join(FILE_WRITE_TOOLS),
                                hooks=[make_spec_only_write_hook(spec_path)],
                            ),
                        ],
                    } if is_onboard else None,
                    permission_mode="bypassPermissions",
                    max_turns=100,
                    cwd=str(self.project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                    env=sdk_env,
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
        except Exception as e:
            logger.exception("Failed to create Claude client")
            yield {
                "type": "error",
                "content": format_client_init_error(e)
            }
            return

        # Start the conversation
        try:
            async with self._query_lock:
                opening = "Begin the project onboarding process." if is_onboard else "Begin the project expansion process."
                async for chunk in self._query_claude(opening):
                    yield chunk
            yield {"type": "response_done"}
        except Exception:
            logger.exception("Failed to start expand chat")
            yield {
                "type": "error",
                "content": "Failed to start conversation"
            }

    async def send_message(
        self,
        user_message: str,
        attachments: list[FileAttachment] | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        Send user message and stream Claude's response.

        Args:
            user_message: The user's response
            attachments: Optional list of image attachments

        Yields:
            Message chunks of various types:
            - {"type": "text", "content": str}
            - {"type": "features_created", "count": N, "features": [...]}
            - {"type": "expansion_complete", "total_added": N}
            - {"type": "error", "content": str}
        """
        if not self.client:
            yield {
                "type": "error",
                "content": "Session not initialized. Call start() first."
            }
            return

        # Store the user message
        self.messages.append({
            "role": "user",
            "content": user_message,
            "has_attachments": bool(attachments),
            "timestamp": datetime.now().isoformat()
        })

        try:
            # Use lock to prevent concurrent queries from corrupting the response stream
            async with self._query_lock:
                async for chunk in self._query_claude(user_message, attachments):
                    yield chunk
            yield {"type": "response_done"}
        except Exception:
            logger.exception("Error during Claude query")
            yield {
                "type": "error",
                "content": "Error while processing message"
            }

    async def _query_claude(
        self,
        message: str,
        attachments: list[FileAttachment] | None = None
    ) -> AsyncGenerator[dict, None]:
        """
        Internal method to query Claude and stream responses.

        Feature creation is handled by Claude calling the feature_create_bulk
        MCP tool directly -- no text parsing needed.
        """
        if not self.client:
            return

        # Build the message content
        if attachments and len(attachments) > 0:
            content_blocks: list[dict[str, Any]] = []
            if message:
                content_blocks.append({"type": "text", "text": message})

            # Add attachment blocks (images as image blocks, documents as extracted text)
            try:
                content_blocks.extend(build_attachment_content_blocks(attachments))
            except DocumentExtractionError as e:
                yield {"type": "error", "content": str(e)}
                return

            await self.client.query(make_multimodal_message(content_blocks))
            logger.info(f"Sent multimodal message with {len(attachments)} attachment(s)")
        else:
            await self.client.query(message)

        # Tool use IDs of pending feature_create_bulk calls, to count created features
        pending_bulk_creates: set[str] = set()

        # Stream the response
        try:
            async for msg in safe_receive_response(self.client, logger):
                msg_type = type(msg).__name__

                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__

                        if block_type == "TextBlock" and hasattr(block, "text"):
                            text = block.text
                            if text:
                                yield {"type": "text", "content": text}

                                self.messages.append({
                                    "role": "assistant",
                                    "content": text,
                                    "timestamp": datetime.now().isoformat()
                                })

                        elif block_type == "ToolUseBlock" and getattr(block, "name", "") == "mcp__features__feature_create_bulk":
                            pending_bulk_creates.add(getattr(block, "id", ""))

                elif msg_type == "UserMessage" and isinstance(getattr(msg, "content", None), list):
                    for block in msg.content:
                        tool_use_id = getattr(block, "tool_use_id", None)
                        if type(block).__name__ != "ToolResultBlock" or tool_use_id not in pending_bulk_creates:
                            continue
                        pending_bulk_creates.discard(tool_use_id)
                        if getattr(block, "is_error", False):
                            continue
                        created = _parse_created_count(getattr(block, "content", None))
                        if created > 0:
                            self.features_created += created
                            yield {"type": "features_created", "count": created, "features": []}
        except Exception as exc:
            is_rate_limit, _ = check_rate_limit_error(exc)
            if is_rate_limit:
                logger.warning(f"Rate limited: {exc}")
                yield {"type": "error", "content": "Rate limited. Please try again later."}
                return
            raise

    def get_features_created(self) -> int:
        """Get the total number of features created in this session."""
        return self.features_created

    def is_complete(self) -> bool:
        """Check if expansion session is complete."""
        return self.complete

    def get_messages(self) -> list[dict]:
        """Get all messages in the conversation."""
        return self.messages.copy()


def _parse_created_count(content: Any) -> int:
    """Extract the "created" count from a feature_create_bulk tool result."""
    if isinstance(content, list):
        content = "".join(
            item.get("text", "") for item in content if isinstance(item, dict)
        )
    if not isinstance(content, str):
        return 0
    try:
        data = json.loads(content)
        # MCP tool results may arrive wrapped as {"result": "<tool JSON>"}
        if isinstance(data, dict) and isinstance(data.get("result"), str):
            data = json.loads(data["result"])
    except ValueError:
        return 0
    created = data.get("created") if isinstance(data, dict) else None
    return created if isinstance(created, int) else 0


# Session registry with thread safety
_expand_sessions: dict[str, ExpandChatSession] = {}
_expand_sessions_lock = threading.Lock()


def get_expand_session(project_name: str) -> Optional[ExpandChatSession]:
    """Get an existing expansion session for a project."""
    with _expand_sessions_lock:
        return _expand_sessions.get(project_name)


async def create_expand_session(
    project_name: str, project_dir: Path, mode: ExpandMode = "expand"
) -> ExpandChatSession:
    """Create a new expansion session for a project, closing any existing one."""
    old_session: Optional[ExpandChatSession] = None

    with _expand_sessions_lock:
        old_session = _expand_sessions.pop(project_name, None)
        session = ExpandChatSession(project_name, project_dir, mode)
        _expand_sessions[project_name] = session

    if old_session:
        try:
            await old_session.close()
        except Exception as e:
            logger.warning(f"Error closing old expand session for {project_name}: {e}")

    return session


async def remove_expand_session(project_name: str) -> None:
    """Remove and close an expansion session."""
    session: Optional[ExpandChatSession] = None

    with _expand_sessions_lock:
        session = _expand_sessions.pop(project_name, None)

    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing expand session for {project_name}: {e}")


def list_expand_sessions() -> list[str]:
    """List all active expansion session project names."""
    with _expand_sessions_lock:
        return list(_expand_sessions.keys())


async def cleanup_all_expand_sessions() -> None:
    """Close all active expansion sessions. Called on server shutdown."""
    sessions_to_close: list[ExpandChatSession] = []

    with _expand_sessions_lock:
        sessions_to_close = list(_expand_sessions.values())
        _expand_sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing expand session {session.project_name}: {e}")
