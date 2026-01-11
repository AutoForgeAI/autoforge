"""
Assistant Chat Session
======================

Manages read-only conversational assistant sessions for projects.
The assistant can answer questions about the codebase and features
but cannot modify any files.
"""

import json
import logging
import os
import shutil
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from .assistant_database import (
    add_message,
    create_conversation,
)

logger = logging.getLogger(__name__)

# Root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent

# Read-only feature MCP tools (no mark_passing, skip, create_bulk)
READONLY_FEATURE_MCP_TOOLS = [
    "mcp__features__feature_get_stats",
    "mcp__features__feature_get_next",
    "mcp__features__feature_get_for_regression",
]

# Action tools for the Architect Assistant
ASSISTANT_ACTION_TOOLS = [
    "mcp__assistant__assistant_create_feature",
    "mcp__assistant__assistant_list_phases",
    "mcp__assistant__assistant_create_phase",
    "mcp__assistant__assistant_get_project_status",
    "mcp__assistant__assistant_get_agent_status",
    "mcp__assistant__assistant_start_agent",
    "mcp__assistant__assistant_stop_agent",
    "mcp__assistant__assistant_pause_agent",
    "mcp__assistant__assistant_resume_agent",
    "mcp__assistant__assistant_check_migration",
    "mcp__assistant__assistant_run_migration",
    "mcp__assistant__assistant_add_task",
    "mcp__assistant__assistant_set_task_dependencies",
    "mcp__assistant__assistant_submit_phase",
    "mcp__assistant__assistant_approve_phase",
]

# Read-only built-in tools (no Write, Edit, Bash)
READONLY_BUILTIN_TOOLS = [
    "Read",
    "Glob",
    "Grep",
    "WebFetch",
    "WebSearch",
]


def get_system_prompt(project_name: str, project_dir: Path) -> str:
    """Generate the system prompt for the Architect Assistant with project context."""
    # Try to load app_spec.txt for context
    app_spec_content = ""
    app_spec_path = project_dir / "prompts" / "app_spec.txt"
    if app_spec_path.exists():
        try:
            app_spec_content = app_spec_path.read_text(encoding="utf-8")
            # Truncate if too long
            if len(app_spec_content) > 5000:
                app_spec_content = app_spec_content[:5000] + "\n... (truncated)"
        except Exception as e:
            logger.warning(f"Failed to read app_spec.txt: {e}")

    return f"""You are the **Architect Assistant** for the "{project_name}" project.

You are the central command hub for project management. Your role is to:
1. **Understand the Project**: Answer questions about the codebase, architecture, and progress
2. **Plan Features**: Help design and create new features with tasks
3. **Manage Development**: Control coding agents, set YOLO modes, manage phases
4. **Facilitate Migration**: Help upgrade projects to the v2 schema
5. **Coordinate Work**: Set task dependencies, submit phases for approval

## Project Specification

{app_spec_content if app_spec_content else "(No app specification found)"}

## Your Capabilities

### Reading & Understanding
- **Read**: Read file contents to understand code
- **Glob**: Find files by pattern (e.g., "**/*.tsx")
- **Grep**: Search file contents with regex
- **WebFetch/WebSearch**: Look up documentation online
- **feature_get_stats**: Get feature completion progress

### Creating & Managing Features
- **assistant_create_feature**: Create a new feature with tasks
- **assistant_add_task**: Add tasks to existing features
- **assistant_set_task_dependencies**: Set which tasks depend on others
- **assistant_list_phases**: See all development phases
- **assistant_create_phase**: Create new development phases

### Agent Control
- **assistant_get_agent_status**: Check if coding agent is running
- **assistant_start_agent**: Start the coding agent (with optional YOLO mode)
- **assistant_stop_agent**: Stop the coding agent
- **assistant_pause_agent**: Pause the agent
- **assistant_resume_agent**: Resume a paused agent

### Phase Workflow
- **assistant_get_project_status**: Get full project overview
- **assistant_submit_phase**: Submit a phase for approval
- **assistant_approve_phase**: Approve a completed phase

### Migration
- **assistant_check_migration**: Check if migration is needed
- **assistant_run_migration**: Migrate to v2 schema

## How to Help Users

### When asked about the project:
1. Use `assistant_get_project_status` to get an overview
2. Read relevant files to understand architecture
3. Provide clear, actionable information

### When asked to add a feature:
1. Discuss what the feature should accomplish
2. Break it down into logical tasks
3. Use `assistant_create_feature` to create it with tasks
4. Suggest dependencies if tasks should run in order

### When asked to start development:
1. Check current status with `assistant_get_project_status`
2. Ask about YOLO mode preference if not specified
3. Start the agent with `assistant_start_agent`

### When asked about migration:
1. Use `assistant_check_migration` to assess
2. Explain what migration does
3. Run migration with `assistant_run_migration` if requested

## Guidelines

1. Be proactive - suggest next steps after completing actions
2. Confirm understanding before creating features with many tasks
3. Provide progress updates when performing multi-step operations
4. If an action fails, explain why and suggest alternatives
5. Reference specific file paths when discussing code"""


class AssistantChatSession:
    """
    Manages a read-only assistant conversation for a project.

    Uses Claude Opus 4.5 with only read-only tools enabled.
    Persists conversation history to SQLite.
    """

    def __init__(self, project_name: str, project_dir: Path, conversation_id: Optional[int] = None):
        """
        Initialize the session.

        Args:
            project_name: Name of the project
            project_dir: Absolute path to the project directory
            conversation_id: Optional existing conversation ID to resume
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self.conversation_id = conversation_id
        self.client: Optional[ClaudeSDKClient] = None
        self._client_entered: bool = False
        self.created_at = datetime.now()

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

    async def start(self) -> AsyncGenerator[dict, None]:
        """
        Initialize session with the Claude client.

        Creates a new conversation if none exists, then sends an initial greeting.
        Yields message chunks as they stream in.
        """
        # Create a new conversation if we don't have one
        if self.conversation_id is None:
            conv = create_conversation(self.project_dir, self.project_name)
            self.conversation_id = conv.id
            yield {"type": "conversation_created", "conversation_id": self.conversation_id}

        # Build permissions list for Architect Assistant
        permissions_list = [
            "Read(./**)",
            "Glob(./**)",
            "Grep(./**)",
            "WebFetch",
            "WebSearch",
            *READONLY_FEATURE_MCP_TOOLS,
            *ASSISTANT_ACTION_TOOLS,
        ]

        # Create security settings file
        security_settings = {
            "sandbox": {"enabled": False},  # No bash, so sandbox not needed
            "permissions": {
                "defaultMode": "bypassPermissions",  # Read-only, no dangerous ops
                "allow": permissions_list,
            },
        }
        settings_file = self.project_dir / ".claude_assistant_settings.json"
        with open(settings_file, "w") as f:
            json.dump(security_settings, f, indent=2)

        # Build MCP servers config - features MCP for reading, assistant for actions
        mcp_servers = {
            "features": {
                "command": sys.executable,
                "args": ["-m", "mcp_server.feature_mcp"],
                "env": {
                    **os.environ,
                    "PROJECT_DIR": str(self.project_dir.resolve()),
                    "PYTHONPATH": str(ROOT_DIR.resolve()),
                },
            },
            "assistant": {
                "command": sys.executable,
                "args": ["-m", "mcp_server.assistant_actions_mcp"],
                "env": {
                    **os.environ,
                    "PROJECT_DIR": str(self.project_dir.resolve()),
                    "PYTHONPATH": str(ROOT_DIR.resolve()),
                },
            },
        }

        # Get system prompt with project context
        system_prompt = get_system_prompt(self.project_name, self.project_dir)

        # Use system Claude CLI
        system_cli = shutil.which("claude")

        try:
            self.client = ClaudeSDKClient(
                options=ClaudeAgentOptions(
                    model="claude-opus-4-5-20251101",
                    cli_path=system_cli,
                    system_prompt=system_prompt,
                    allowed_tools=[
                        *READONLY_BUILTIN_TOOLS,
                        *READONLY_FEATURE_MCP_TOOLS,
                        *ASSISTANT_ACTION_TOOLS,
                    ],
                    mcp_servers=mcp_servers,
                    permission_mode="bypassPermissions",
                    max_turns=100,
                    cwd=str(self.project_dir.resolve()),
                    settings=str(settings_file.resolve()),
                )
            )
            await self.client.__aenter__()
            self._client_entered = True
        except Exception as e:
            logger.exception("Failed to create Claude client")
            yield {"type": "error", "content": f"Failed to initialize assistant: {str(e)}"}
            return

        # Send initial greeting
        try:
            greeting = f"""Hello! I'm your **Architect Assistant** for **{self.project_name}**.

I'm your central command hub for managing this project. I can help you:

- **Understand the codebase** - Ask me about any file, feature, or architecture decision
- **Add new features** - Describe what you want to build and I'll create features with tasks
- **Manage development** - Start/stop/pause the coding agent, set YOLO modes
- **Track progress** - View phase status, task completion, dependencies
- **Handle migrations** - Upgrade to the v2 schema if needed

What would you like to do?"""

            # Store the greeting in the database
            add_message(self.project_dir, self.conversation_id, "assistant", greeting)

            yield {"type": "text", "content": greeting}
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Failed to send greeting")
            yield {"type": "error", "content": f"Failed to start conversation: {str(e)}"}

    async def send_message(self, user_message: str) -> AsyncGenerator[dict, None]:
        """
        Send user message and stream Claude's response.

        Args:
            user_message: The user's message

        Yields:
            Message chunks:
            - {"type": "text", "content": str}
            - {"type": "tool_call", "tool": str, "input": dict}
            - {"type": "response_done"}
            - {"type": "error", "content": str}
        """
        if not self.client:
            yield {"type": "error", "content": "Session not initialized. Call start() first."}
            return

        if self.conversation_id is None:
            yield {"type": "error", "content": "No conversation ID set."}
            return

        # Store user message in database
        add_message(self.project_dir, self.conversation_id, "user", user_message)

        try:
            async for chunk in self._query_claude(user_message):
                yield chunk
            yield {"type": "response_done"}
        except Exception as e:
            logger.exception("Error during Claude query")
            yield {"type": "error", "content": f"Error: {str(e)}"}

    async def _query_claude(self, message: str) -> AsyncGenerator[dict, None]:
        """
        Internal method to query Claude and stream responses.

        Handles tool calls and text responses.
        """
        if not self.client:
            return

        # Send message to Claude
        await self.client.query(message)

        full_response = ""

        # Stream the response
        async for msg in self.client.receive_response():
            msg_type = type(msg).__name__

            if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__

                    if block_type == "TextBlock" and hasattr(block, "text"):
                        text = block.text
                        if text:
                            full_response += text
                            yield {"type": "text", "content": text}

                    elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                        tool_name = block.name
                        tool_input = getattr(block, "input", {})
                        yield {
                            "type": "tool_call",
                            "tool": tool_name,
                            "input": tool_input,
                        }

        # Store the complete response in the database
        if full_response and self.conversation_id:
            add_message(self.project_dir, self.conversation_id, "assistant", full_response)

    def get_conversation_id(self) -> Optional[int]:
        """Get the current conversation ID."""
        return self.conversation_id


# Session registry with thread safety
_sessions: dict[str, AssistantChatSession] = {}
_sessions_lock = threading.Lock()


def get_session(project_name: str) -> Optional[AssistantChatSession]:
    """Get an existing session for a project."""
    with _sessions_lock:
        return _sessions.get(project_name)


async def create_session(
    project_name: str,
    project_dir: Path,
    conversation_id: Optional[int] = None
) -> AssistantChatSession:
    """
    Create a new session for a project, closing any existing one.

    Args:
        project_name: Name of the project
        project_dir: Absolute path to the project directory
        conversation_id: Optional conversation ID to resume
    """
    old_session: Optional[AssistantChatSession] = None

    with _sessions_lock:
        old_session = _sessions.pop(project_name, None)
        session = AssistantChatSession(project_name, project_dir, conversation_id)
        _sessions[project_name] = session

    if old_session:
        try:
            await old_session.close()
        except Exception as e:
            logger.warning(f"Error closing old session for {project_name}: {e}")

    return session


async def remove_session(project_name: str) -> None:
    """Remove and close a session."""
    session: Optional[AssistantChatSession] = None

    with _sessions_lock:
        session = _sessions.pop(project_name, None)

    if session:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing session for {project_name}: {e}")


def list_sessions() -> list[str]:
    """List all active session project names."""
    with _sessions_lock:
        return list(_sessions.keys())


async def cleanup_all_sessions() -> None:
    """Close all active sessions. Called on server shutdown."""
    sessions_to_close: list[AssistantChatSession] = []

    with _sessions_lock:
        sessions_to_close = list(_sessions.values())
        _sessions.clear()

    for session in sessions_to_close:
        try:
            await session.close()
        except Exception as e:
            logger.warning(f"Error closing session {session.project_name}: {e}")
