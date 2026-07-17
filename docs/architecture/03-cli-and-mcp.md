# CLI Usage & Feature MCP Server

## Overview

AutoForge provides four distinct entry points for running agents and managing projects:
1. **`autoforge` npm CLI** - Production use (global install)
2. **`start_ui.py`** - Development use (from source)
3. **`start.py`** - Interactive terminal menu
4. **`autonomous_agent_demo.py`** - Direct agent invocation

## CLI Entry Points

### 1. `autoforge` (npm Global CLI)

**Files:** `bin/autoforge.js`, `lib/cli.js`

The npm global package (`autoforge-ai`) is a zero-dependency Node.js wrapper that manages the Python environment and server lifecycle.

**Commands:**
```bash
autoforge                       # Start server (default)
autoforge config                # Open ~/.autoforge/.env in $EDITOR
autoforge config --path         # Print config file path
autoforge config --show         # Show effective configuration
autoforge --version / -v        # Print version
autoforge --help / -h           # Show help
```

**Server Start Options:**
```bash
autoforge --port PORT           # Custom port (default: auto-detect from 8888)
autoforge --host HOST           # Custom host (default: 127.0.0.1)
autoforge --no-browser          # Don't auto-open browser
autoforge --repair              # Delete and recreate venv
autoforge --dev                 # Blocked; requires cloned repo
```

**What it does:**
1. **Python detection**: Searches platform-specific candidates. Requires 3.11+. `AUTOFORGE_PYTHON` env var overrides.
2. **Venv management**: Creates venv at `~/.autoforge/venv/`. Uses a composite marker containing requirements hash + Python version. Recreates if Python version changed or requirements hash differs.
3. **Config management**: Copies `.env.example` to `~/.autoforge/.env` on first run.
4. **Server startup**: Spawns `uvicorn server.main:app`, writes PID file, handles signal cleanup, opens browser after 2s delay.
5. **Playwright CLI check**: Verifies `playwright-cli` is available, installs via `npm install -g @playwright/cli` if missing.

### 2. `start_ui.py` (Development Server)

**Usage:**
```bash
python start_ui.py              # Production mode
python start_ui.py --dev        # Development mode with Vite hot reload
python start_ui.py --host 0.0.0.0  # Remote access
python start_ui.py --port 9999  # Custom port
```

**What it does:**
1. Creates/activates Python venv at `./venv`
2. Installs Python dependencies from `requirements.txt`
3. Checks Node.js availability
4. Installs npm dependencies if stale
5. Builds React frontend if source files changed
6. Starts server:
   - **Dev mode**: Spawns both FastAPI (uvicorn `--reload`) and Vite dev server
   - **Production mode**: Spawns uvicorn without `--reload`

### 3. `start.py` (Interactive Terminal Menu)

**Usage:**
```bash
python start.py
```

Provides an interactive menu:
- `[1] Create new project` - Name, path, spec creation (Claude-assisted or manual)
- `[2] Continue existing project` - Select from registered projects
- `[q] Quit`

For spec creation, offers two paths:
- **Claude path**: Launches `claude /create-spec {project_dir}` subprocess
- **Manual path**: Shows template file paths for manual editing

### 4. `autonomous_agent_demo.py` (Direct Agent Invocation)

This is the primary entry point for running agents from the command line, both inside and outside of Claude Code.

**Complete Argument Reference:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--project-dir` | str | **required** | Absolute path or registered project name |
| `--max-iterations` | int | None (unlimited) | Max agent iterations (typically 1 for subprocesses) |
| `--model` | str | `DEFAULT_MODEL` | Claude model to use |
| `--yolo` | flag | False | Skip testing agents for rapid prototyping |
| `--concurrency` / `-c` | int | 1 | Concurrent coding agents, max 5 |
| `--parallel` / `-p` | int | None | **DEPRECATED** alias for `--concurrency` |
| `--feature-id` | int | None | Work on specific feature ID |
| `--feature-ids` | str | None | Comma-separated feature IDs for batch (e.g., `'5,8,12'`) |
| `--agent-type` | choice | None | `initializer`, `coding`, or `testing` |
| `--testing-feature-id` | int | None | Feature ID for regression test (legacy) |
| `--testing-feature-ids` | str | None | Comma-separated feature IDs for batch testing |
| `--testing-ratio` | int | 1 | Testing agents per coding agent (0-3) |
| `--testing-batch-size` | int | 3 | Features per testing batch (1-5) |
| `--batch-size` | int | 3 | Max features per coding agent batch (1-3) |

**Examples:**
```bash
# Basic single-agent run
python autonomous_agent_demo.py --project-dir /path/to/my-app

# By registered project name
python autonomous_agent_demo.py --project-dir my-app

# YOLO mode (skip testing)
python autonomous_agent_demo.py --project-dir my-app --yolo

# Parallel with 3 concurrent agents
python autonomous_agent_demo.py --project-dir my-app -c 3

# Specific feature only
python autonomous_agent_demo.py --project-dir my-app --feature-id 42

# Batch multiple features
python autonomous_agent_demo.py --project-dir my-app --feature-ids 5,8,12

# Run as specific agent type (used by orchestrator internally)
python autonomous_agent_demo.py --project-dir my-app --agent-type initializer
python autonomous_agent_demo.py --project-dir my-app --agent-type coding --feature-id 42
python autonomous_agent_demo.py --project-dir my-app --agent-type testing --testing-feature-ids 5,12
```

**Project Resolution:**
1. If `--project-dir` is an absolute path and exists, use as-is
2. Otherwise, look up by name in the registry (`~/.autoforge/registry.db`)

## Usage Inside Claude Code

### Slash Commands

Located in `.claude/commands/`. Six commands available:

| Command | Purpose |
|---------|---------|
| `/create-spec` | Interactive spec creation for new projects (7-phase conversation) |
| `/expand-project` | Add features to existing projects via natural language |
| `/check-code` | Run lint (`ruff`), security tests, and UI build |
| `/checkpoint` | Create comprehensive checkpoint git commit |
| `/review-pr` | Review pull requests with complexity-proportional depth |
| `/gsd-to-autoforge-spec` | Convert GSD codebase mapping to AutoForge spec format |

### How the Agent Interacts with AutoForge

When a coding agent session runs, it:
1. Reads the coding prompt (from `.autoforge/prompts/coding_prompt.md`)
2. Connects to the Feature MCP server for progress tracking
3. Claims a feature via `feature_claim_and_get` or `feature_mark_in_progress`
4. Implements the feature following the step-by-step workflow
5. Marks the feature as passing/failing via MCP tools
6. Commits progress and updates `claude-progress.txt`

---

## Feature MCP Server

### Architecture

**File:** `mcp_server/feature_mcp.py`

Built on the `FastMCP` framework from the `mcp` package. Communicates over **stdio** (standard MCP transport).

The MCP server is spawned as a child process of the Claude CLI. Configuration in `client.py`:

```python
mcp_servers = {
    "features": {
        "command": sys.executable,
        "args": ["-m", "mcp_server.feature_mcp"],
        "env": {
            "PROJECT_DIR": str(project_dir.resolve()),
            "PYTHONPATH": str(Path(__file__).parent.resolve()),
        },
    },
}
```

### Running the MCP Server Independently

The MCP server can be run standalone from the command line:

```bash
PROJECT_DIR=/path/to/project PYTHONPATH=/path/to/autoforge python -m mcp_server.feature_mcp
```

This starts the server on stdio, expecting MCP protocol messages. You can interact with it using any MCP client (e.g., the `mcp` CLI tool, or a custom client).

### All MCP Tools

| Tool | Purpose |
|------|---------|
| `feature_get_stats` | Progress stats: passing, in_progress, needs_human_input, total, percentage |
| `feature_get_by_id` | Full feature details by ID |
| `feature_get_summary` | Minimal info: id, name, passes, in_progress, dependencies |
| `feature_mark_passing` | Mark feature passing + clear in_progress (atomic, idempotent) |
| `feature_mark_failing` | Mark feature failing (regression detected) |
| `feature_skip` | Move to end of priority queue + clear in_progress |
| `feature_mark_in_progress` | Atomically claim feature (fails if already claimed/passing/needs_human_input) |
| `feature_claim_and_get` | Atomic claim + return full details (idempotent for parallel mode) |
| `feature_clear_in_progress` | Release feature back to pending queue |
| `feature_create_bulk` | Create multiple features with index-based dependencies and cycle detection |
| `feature_create` | Create single feature with auto-priority |
| `feature_add_dependency` | Add dependency with circular dependency check |
| `feature_remove_dependency` | Remove a dependency |
| `feature_get_ready` | Get features with all deps satisfied, sorted by scheduling score |
| `feature_get_blocked` | Get features blocked by unmet dependencies |
| `feature_get_graph` | Dependency graph data (nodes + edges) for visualization |
| `feature_set_dependencies` | Replace all dependencies for a feature |
| `feature_request_human_input` | Block feature waiting for human input (structured form fields) |
| `ask_user` | Ask user structured questions with selectable options |

### Tool Availability by Agent Type

Tools are filtered per agent type in `client.py` to reduce schema overhead and prevent misuse. The `allowed_tools` list controls what the LLM sees; all tools remain permitted at the security layer so the MCP server can respond if called.

`feature_remove_dependency` is intentionally omitted from all agent tool lists (available only via the UI/REST API).

| Tool | Coding | Testing | Initializer |
|------|--------|---------|-------------|
| `feature_get_stats` | Yes | Yes | Yes |
| `feature_get_by_id` | Yes | Yes | - |
| `feature_get_summary` | Yes | Yes | - |
| `feature_get_ready` | Yes | Yes | Yes |
| `feature_get_blocked` | Yes | Yes | Yes |
| `feature_get_graph` | Yes | Yes | Yes |
| `feature_claim_and_get` | Yes | - | - |
| `feature_mark_in_progress` | Yes | - | - |
| `feature_mark_passing` | Yes | Yes | - |
| `feature_mark_failing` | Yes | Yes | - |
| `feature_skip` | Yes | - | - |
| `feature_clear_in_progress` | Yes | - | - |
| `feature_create_bulk` | - | - | Yes |
| `feature_create` | - | - | Yes |
| `feature_add_dependency` | - | - | Yes |
| `feature_set_dependencies` | - | - | Yes |

### MCP Tool Naming Convention

MCP tools are exposed to the agent with the prefix `mcp__features__`. For example:
- `mcp__features__feature_mark_passing`
- `mcp__features__feature_get_stats`
- `mcp__features__feature_claim_and_get`

This is the Claude Agent SDK's namespacing convention: `mcp__{server_name}__{tool_name}`.

### Database Operations & Concurrency

All state-changing operations use **atomic SQL** (not Python locks) for parallel safety:

- `feature_mark_passing`: Uses `WHERE passes = 0` guard to prevent double-pass
- `feature_mark_in_progress`: Uses `WHERE passes = 0 AND in_progress = 0 AND needs_human_input = 0`
- `feature_skip`: Sets `priority = (SELECT MAX(priority) + 1)` atomically
- `feature_create_bulk`: Uses `atomic_transaction` context manager for bulk inserts

This design allows multiple agents to safely interact with the same `features.db` simultaneously.

## REST API (Server)

The FastAPI server (`server/main.py`) provides REST and WebSocket endpoints for the UI and programmatic access:

### Key Endpoint Groups

| Router | Prefix | Purpose |
|--------|--------|---------|
| `projects` | `/api/projects` | Project CRUD with registry |
| `features` | `/api/projects/{name}/features` | Feature management (REST, independent of MCP) |
| `agent` | `/api/projects/{name}/agent` | Agent start/stop/pause/resume |
| `schedules` | `/api/projects/{name}/schedules` | Time-based agent scheduling |
| `devserver` | `/api/projects/{name}/devserver` | Dev server start/stop |
| `spec_creation` | WebSocket | Interactive spec creation |
| `expand_project` | WebSocket | Project expansion via chat |
| `filesystem` | `/api/filesystem` | Filesystem browser API |
| `assistant_chat` | WebSocket + REST | Read-only project Q&A |
| `settings` | `/api/settings` | Global settings management |
| `terminal` | WebSocket | PTY terminal I/O |

### Real-time Updates

WebSocket endpoint: `/ws/projects/{project_name}`

Message types:
- `progress` - Test pass counts (passing, in_progress, total)
- `agent_status` - Running/paused/stopped/crashed
- `log` - Agent output lines (with optional featureId/agentIndex)
- `feature_update` - Feature status changes
- `agent_update` - Multi-agent state (thinking/working/testing/success/error)

### Health & Setup Endpoints

- `GET /api/health` - Health check
- `GET /api/setup/status` - System setup status (Claude CLI, Node.js, credentials)

### Security

- Localhost-only middleware when `AUTOFORGE_ALLOW_REMOTE` is not set
- CORS restricted to localhost:5173 and localhost:8888 by default
- Path traversal protection on static file serving

## Execution Flow Diagram

```
User
  |
  +-- npm: `autoforge` --------------> lib/cli.js
  |                                     |
  |                                     +-> findPython() -> ensureVenv()
  |                                     +-> spawn uvicorn server.main:app
  |                                             |
  +-- python: `start_ui.py` ------>  setup venv + npm + build
  |                                     +-> spawn uvicorn server.main:app
  |                                             |
  +-- python: `start.py` --------->  interactive menu
  |                                     +-> subprocess: autonomous_agent_demo.py
  |                                             |
  +-- python: `autonomous_agent_demo.py` --> parallel_orchestrator
                                                |
                                                +-> subprocess: --agent-type initializer
                                                +-> subprocess: --agent-type coding --feature-id N
                                                +-> subprocess: --agent-type testing --testing-feature-ids X,Y
                                                        |
                                                        +-> agent.py: run_autonomous_agent()
                                                              +-> client.py: ClaudeSDKClient
                                                                    +-> spawns: python -m mcp_server.feature_mcp
                                                                    +-> spawns: claude CLI subprocess
```
