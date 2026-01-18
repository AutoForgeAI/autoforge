# CLAUDE.md

Instructions for Claude Code (claude.ai/code) when working with this fork.

**This is a fork of [Leon van Zyl's original AutoCoder](https://github.com/leonvanzyl/autocoder) with parallel agents, knowledge base, and modern packaging.**

Leon built the brilliant single-agent foundation. I added the ability to run multiple agents in parallel while they learn from each other.

---

## Quick Overview

This is an autonomous coding system that uses Claude to build complete applications. It's got:

1. **Spec Chat** - Interactive Q&A to create your project spec
2. **Assistant Chat** - Plan and manage features mid-development
3. **Coding Agent** - Actually implements stuff autonomously
4. **Parallel Agents** - Run 3-5 agents at once (3x faster, the killer feature)

The AI is shockingly good at this when you give it clear specs. It's not going to replace your dev team, but it's surprisingly capable.

---

## How to Use This Fork

### Installation (The Modern Way)

```bash
# Install everything (including dev tools)
pip install -e '.[dev]'

# That's it. The CLI handles the rest.
```

### Running It

```bash
# Just run this - it'll check setup and ask what you want
autocoder

# Launch Web UI directly
autocoder-ui

# Run single agent
autocoder agent --project-dir my-app

# Run parallel agents (where the magic happens)
autocoder parallel --project-dir my-app --parallel 3 --preset balanced
```

**What's different from the original:**
- One command (`autocoder`) instead of remembering `start.py`, `agent_manager.py`, etc.
- Auto-setup handles the UI build for you
- Everything is a proper Python package now (2026 standards, not 2015)
- All the old scripts still work (I made shims for backward compatibility)

---

## Package Structure (Post-Migration)

```
src/autocoder/
├── cli.py                # Unified CLI (asks what you want)
├── core/                 # The parallel agent system
│   ├── orchestrator.py   # Manages multiple agents
│   ├── gatekeeper.py     # Verifies and merges code
│   ├── worktree_manager.py # Git worktree isolation
│   ├── knowledge_base.py # Learns from patterns
│   ├── model_settings.py # Model selection
│   ├── test_framework_detector.py # Auto-detects tests
│   └── database.py       # SQLite wrapper
├── agent/                # Agent implementation
│   ├── agent.py          # Session loop
│   ├── client.py         # Claude SDK client
│   ├── prompts.py        # Prompt templates
│   ├── progress.py       # Progress tracking
│   ├── registry.py       # Project registry
│   └── security.py       # Command validation
├── server/               # FastAPI backend
│   ├── routers/          # API endpoints
│   ├── services/         # Business logic
│   └── websocket.py      # Real-time updates
├── tools/                # MCP tools
│   ├── test_mcp.py       # Test framework detection
│   ├── knowledge_mcp.py  # Knowledge base queries
│   ├── model_settings_mcp.py # Model selection
│   └── feature_mcp.py    # Feature management
└── api/                  # Database models
```

**Root directory** still has the old scripts (backward compatibility):
- `start.py` - Works, but you should use `autocoder` instead
- `agent.py` - Legacy shim
- `autonomous_agent_demo.py` - Legacy shim
- `orchestrator_demo.py` - Legacy shim
- All re-export from the new package structure

---

## Project Registry

Projects live wherever you want them. The registry (`~/.autocoder/registry.db`) maps names to paths:

```python
# Register a project
from autocoder.agent import register_project
register_project("my-app", Path("/path/to/project"))

# Look it up later
from autocoder.agent import get_project_path
path = get_project_path("my-app")
```

Uses SQLite with cross-platform path handling (POSIX-style forward slashes everywhere).

---

## Feature Management (Via MCP)

Features live in SQLite (`features.db`). The agent talks to them through MCP tools:

**Agent tools:**
- `feature_get_stats` - Progress stats
- `feature_get_next` - Get next feature to build
- `feature_get_for_regression` - Random passing features for testing
- `feature_mark_passing` - Mark feature done
- `feature_skip` - Move to end of queue
- `feature_create_bulk` - Initialize all features

**Assistant Chat tools:**
- `feature_get_all` - List all features
- `feature_get_by_id` - Get specific feature
- `feature_update` - Modify a feature
- `feature_delete` - Remove a feature

---

## Assistant Chat (The Planning Helper)

Press `A` in the UI to launch this. It's a read-only planning assistant that:

- **Can** read code, search files, manage features, visit your app in browser
- **Cannot** modify files (use coding agent for that)

Perfect for:
- Planning new features mid-development
- Modifying existing feature requirements
- Debugging UI issues (it can take screenshots and test stuff)
- Understanding the codebase without reading 200 files

---

## YOLO Mode (Rapid Prototyping)

Skip testing for faster iteration:

```bash
autocoder agent --project-dir my-app --yolo
```

**What it skips:**
- Regression testing
- Browser automation (Playwright)

**What it keeps:**
- Lint and type-check (still verifies code compiles)
- All the other tools

**When to use:** Early prototyping. Switch back to normal mode for production-quality stuff.

---

## React UI (in ui/)

```bash
cd ui
npm install          # First time only
npm run dev         # Dev server with hot reload
npm run build       # Production build (for autocoder-ui)
npm run lint        # Check code quality
```

Note: `autocoder-ui` serves the pre-built UI from `ui/dist/`. Rebuild after making changes.

UI notes:
- Scheduled runs live in the **Settings** modal (press `S`).
- LAN access: set `AUTOCODER_UI_HOST=0.0.0.0` and `AUTOCODER_UI_ALLOW_REMOTE=1` (restart required).

---

## Parallel Agents (Why This Fork Exists)

This is the killer feature:

1. **Orchestrator** spawns 3-5 agents in isolated git worktrees
2. **Each agent** works on different features simultaneously
3. **Knowledge Base** shares learnings (Agent 1 figures out React testing → Agent 2 benefits)
4. **Gatekeeper** verifies in temporary worktrees (never dirties your main branch)
5. **Smart routing** - Opus for complex stuff, Haiku for simple

Result: 3x faster development without sacrificing quality.

**Model presets:**
- `quality` - Opus only (best, expensive)
- `balanced` - Opus + Haiku (recommended)
- `economy` - Opus + Sonnet + Haiku
- `cheap` - Sonnet + Haiku
- `experimental` - All models

---

## Security Model

Defense-in-depth approach:

1. **OS sandbox** for bash commands
2. **Filesystem** restricted to project directory only
3. **Bash allowlist** in `security.py` (ALLOWED_COMMANDS)

The agent can't just run arbitrary commands. There's a whitelist.

---

## Three-Chat Architecture

Different chats for different phases:

1. **Spec Chat** - Create your project spec upfront
2. **Assistant Chat** - Plan and manage features as you go
3. **Coding Agent** - Actually build the stuff

Workflow:
```
1. Create project → Spec chat makes spec + initial features
2. Development → Assistant chat adds/modifies features as needed
3. Implement → Start coding agent to build features
4. Iterate → Pause agent, chat with assistant, resume
```

---

## What Changed From Original

**My contributions:**
- Modern packaging (`pyproject.toml`, `src/` layout)
- Unified CLI (`autocoder` instead of 10 scripts)
- Auto-setup (handles UI build automatically)
- Fixed import hell (everything properly organized now)

**Original stuff (all theirs):**
- Two-agent pattern
- Parallel execution
- Knowledge base
- Test framework detection
- All the actual AI magic

I just made it easier to use. The hard problems (making AI code autonomously) were already solved.

---

## Development Workflow

```bash
# Install with dev tools
pip install -e '.[dev]'

# Run tests
pytest tests/

# Format code
black .

# Lint
ruff check .

# Type check
mypy src/autocoder
```

---

## Common Tasks

**Import patterns to use:**
```python
# From within the package
from autocoder import Orchestrator, run_autonomous_agent
from autocoder.agent import get_project_path, register_project
from autocoder.core import KnowledgeBase, get_knowledge_base
```

**From root scripts (legacy):**
```python
# Old way (still works via shims)
from agent import run_autonomous_agent
from registry import get_project_path
```

---

**Base System by:** [Leon van Zyl](https://github.com/leonvanzyl) - https://github.com/leonvanzyl/autocoder
- Single-agent autonomous coding system
- React UI and MCP architecture
- Two-agent pattern (initializer + coding)

**Parallel System by:** [Gabi at Booplex](https://booplex.com) - "I tamed AI so you don't have to"
- Orchestrator, Gatekeeper, WorktreeManager, KnowledgeBase
- Modern packaging and unified CLI
- Auto-setup and developer experience improvements
