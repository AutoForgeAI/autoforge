# AutoForge Architecture Documentation

Comprehensive technical documentation covering how AutoForge works internally, how to use it from the command line, and how to customize it for non-standard project types.

## Documents

### [01 - Agent Invocation, Context Window & Session Management](01-agent-invocation.md)

How AutoForge invokes Claude agents, including:
- The two-layer architecture (orchestrator + agent subprocesses)
- How context is preserved across stateless sessions (SQLite, git, progress notes, app spec)
- Context window size configuration (1M token beta header)
- PreCompact hook for within-session context management
- ClaudeSDKClient configuration and agent-type-specific tool lists
- Session management, auto-continue, and rate limit handling
- Process limits for parallel mode

### [02 - Git Operations & Implicit Commits](02-git-operations.md)

All git operations in AutoForge, including:
- When and how git commits happen (initializer, coding, testing agents)
- Git push behavior (never instructed, but not blocked)
- Git in the security model (command-level allowlist, no subcommand filtering)
- Programmatic `.gitignore` management
- Commit timeline across the project lifecycle
- Parallel mode git considerations

### [03 - CLI Usage & Feature MCP Server](03-cli-and-mcp.md)

How to use AutoForge from the command line and how the Feature MCP works:
- Four CLI entry points (`autoforge`, `start_ui.py`, `start.py`, `autonomous_agent_demo.py`)
- Complete argument reference for direct agent invocation
- Slash commands for use inside Claude Code
- Feature MCP server architecture and all 17+ tools
- Tool availability matrix by agent type
- REST API endpoints and WebSocket real-time updates
- Full execution flow diagram

### [04 - Customization Guide](04-customization-guide.md)

How to adapt AutoForge for any project type:
- 10 major customization points (prompts, spec, commands, CLAUDE.md, etc.)
- What to change in coding and initializer prompts for non-web projects
- **Example 1**: Event-Sourced CQRS system with NATS JetStream, Go, and SQLite
- **Example 2**: ESPHome embedded project for ESP32 (YAML-based, compile-only verification)
- General adaptation strategy for any technology stack

## Architecture Decision Records

### [ADR-005: Spec Evolution](adr/ADR-005-spec-evolution.md)

**Status: Proposed** — Linking features to their origin specs:
- Problem: `app_spec.txt` is written once and becomes stale as projects evolve through multiple expansion rounds
- Proposal: Specs table in SQLite (source of truth) with auto-exported markdown projections
- Database changes: `specs` table + `spec_id` foreign key on Feature table
- Spec Workspace UI for authoring, reviewing, and tracking specs
- Git worktrees for parallel spec iterations
- Eight implementation phases from database foundation through worktree support
