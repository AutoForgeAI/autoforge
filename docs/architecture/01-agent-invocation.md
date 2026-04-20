# Agent Invocation, Context Window & Session Management

## Overview

AutoForge uses a two-layer architecture for agent invocation:
1. An **orchestrator** (`parallel_orchestrator.py`) manages the lifecycle of multiple agents
2. Each agent is a **Python subprocess** that uses the `claude-agent-sdk` Python package to start and communicate with a `claude` CLI subprocess

## Agent Invocation Flow

### Entry Point: `autonomous_agent_demo.py`

Two distinct code paths:

**Path A - Entry Point Mode** (no `--agent-type`): The normal user-facing mode. Imports and runs `run_parallel_orchestrator()` which manages all agent lifecycle including initialization, coding, and testing.

**Path B - Subprocess Mode** (with `--agent-type`): Invoked by the orchestrator when it spawns child agent processes. Calls `run_autonomous_agent()` directly with `max_iterations=1`.

### The Orchestrator: `parallel_orchestrator.py`

The `ParallelOrchestrator` manages the full lifecycle:

1. **Phase 1 - Initialization Check**: Calls `has_features(project_dir)` to check if `features.db` has rows. If not, runs `_run_initializer()` as a blocking subprocess.

2. **Phase 2 - Feature Loop**: Main polling loop (5-second interval) that:
   - Queries all features from SQLite
   - Computes dependency-aware scheduling scores
   - Spawns coding agent subprocesses via `_spawn_coding_agent()` or `_spawn_coding_agent_batch()`
   - Maintains testing agents independently via `_maintain_testing_agents()`

3. **Subprocess Spawning**: Each agent is a `subprocess.Popen` call:
   ```python
   cmd = [
       sys.executable,
       "-u",  # Force unbuffered stdout/stderr
       str(AUTOFORGE_ROOT / "autonomous_agent_demo.py"),
       "--project-dir", str(self.project_dir),
       "--max-iterations", "1",
       "--agent-type", "coding",
       "--feature-id", str(feature_id),
   ]
   proc = subprocess.Popen(cmd, **popen_kwargs)
   ```

   Key subprocess configuration:
   - `stdin=subprocess.DEVNULL` - prevents blocking on stdin reads
   - `stdout=subprocess.PIPE, stderr=subprocess.STDOUT` - captures all output
   - `cwd=str(self.project_dir)` - runs from project directory
   - Environment includes `PLAYWRIGHT_CLI_SESSION=f"coding-{feature_id}"` for browser session isolation

### The Agent Session Loop: `agent.py`

`run_autonomous_agent()` implements the main agent loop:

1. **Auto-detect agent type**: If `agent_type` is `None`, checks `has_features()` to decide initializer vs coding.
2. **Per-iteration client creation**: Creates a **fresh client every iteration**:
   ```python
   client = create_client(project_dir, model, yolo_mode=yolo_mode, agent_type=agent_type)
   ```
3. **Prompt selection**: Chooses prompt based on agent type (initializer, testing, coding batch, coding single, or coding general)
4. **Session execution**:
   ```python
   async with client:
       status, response = await run_agent_session(client, prompt, project_dir)
   ```
5. **`run_agent_session()`**: The actual SDK interaction sends a query and iterates over `AssistantMessage` and `UserMessage` responses.

### The Claude Agent SDK Client

The `claude-agent-sdk` package (version `>=0.1.0,<0.2.0`) provides `ClaudeSDKClient` and `ClaudeAgentOptions`.

- **`ClaudeSDKClient` wraps the `claude` CLI** as a subprocess. The CLI path is resolved via `shutil.which("claude")`.
- **`async with client`** starts the CLI subprocess and MCP servers.
- **`client.query(message)`** sends a prompt to the running CLI process.
- **`client.receive_response()`** is an async iterator yielding `AssistantMessage` and `UserMessage` objects.
- **`async with client` exit** shuts down the CLI subprocess and MCP servers.

The SDK communicates with the `claude` CLI over stdin/stdout (JSON protocol), which itself calls the Anthropic API. The SDK does NOT call the API directly -- it delegates to the CLI.

```
┌─────────────────────────────────────────────────────┐
│  Orchestrator (parallel_orchestrator.py)            │
│                                                     │
│  ┌─── subprocess.Popen ──────────────────────────┐  │
│  │  autonomous_agent_demo.py --agent-type coding  │  │
│  │                                                │  │
│  │  ┌── agent.py ─────────────────────────────┐   │  │
│  │  │  ClaudeSDKClient (claude-agent-sdk)      │   │  │
│  │  │                                          │   │  │
│  │  │  ┌── claude CLI subprocess ───────────┐  │   │  │
│  │  │  │  Anthropic API / Vertex AI         │  │   │  │
│  │  │  └────────────────────────────────────┘  │   │  │
│  │  │                                          │   │  │
│  │  │  ┌── MCP Server subprocess ───────────┐  │   │  │
│  │  │  │  python -m mcp_server.feature_mcp   │  │   │  │
│  │  │  └────────────────────────────────────┘  │   │  │
│  │  └──────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────┘  │
│                                                     │
│  (Repeat for each concurrent agent)                  │
└─────────────────────────────────────────────────────┘
```

## Context Window Preservation Between Sessions

**There is NO conversation history carried between sessions.** Each session starts with a fresh `ClaudeSDKClient`. Context is preserved through four persistent mechanisms:

### A. SQLite Database (`features.db`)

The Feature table tracks: `id, priority, category, name, description, steps, passes, in_progress, dependencies`. The agent reads current state via MCP tools (`feature_get_stats`, `feature_get_ready`, `feature_claim_and_get`) at the start of each session.

### B. The Prompt Itself

Each session receives a carefully crafted prompt that includes:
- Full workflow instructions (how to implement, test, commit)
- Feature assignment (single ID or batch IDs)
- References to `app_spec.txt` which the agent reads from the filesystem

### C. The Filesystem (Project Files + Git)

The agent reads files it previously created/modified. Git history provides additional context. The coding prompt instructs the agent to run `git log --oneline -20` at session start. The project's `CLAUDE.md` is loaded automatically via `setting_sources=["project"]`.

### D. Progress Notes (`claude-progress.txt`)

The coding prompt instructs the agent to read `tail -500 claude-progress.txt` at session start and write updates at session end. This serves as a cross-session "memory" document.

### E. The App Spec

`app_spec.txt` lives at `{project_dir}/.autoforge/prompts/app_spec.txt` and is copied to the project root for the agent to read. This provides the high-level specification context that persists across all sessions.

**Key design insight:** The system is designed for **stateless sessions** by construction. Each agent subprocess gets `--max-iterations 1` from the orchestrator, meaning it runs exactly one session and exits. The orchestrator then spawns a new subprocess for the next feature.

## Context Window Size Configuration

### 1M Token Extended Context (Beta)

AutoForge explicitly requests the 1M token context window via a beta header in `client.py`:

```python
betas=[] if is_alternative_api else ["context-1m-2025-08-07"],
```

This is the **only** context window configuration in the codebase. The beta header `"context-1m-2025-08-07"` requests the extended 1M token context window from the Anthropic API.

### Conditional Disabling for Alternative Providers

When using alternative API providers (Ollama, GLM, Kimi, Vertex AI, or any custom provider with a base URL), the `betas` list is set to empty `[]`:

```python
is_vertex = sdk_env.get("CLAUDE_CODE_USE_VERTEX") == "1"
is_alternative_api = bool(base_url) or is_vertex
```

This means alternative providers get their default context window (typically 200k for Anthropic models), not the extended 1M window.

### No Runtime Detection

There is **no code** that detects context window size at runtime, checks for 100k vs 200k vs 1M, reads token counts, or adapts behavior based on available context. The system takes a binary approach: either request the 1M beta or don't.

### PreCompact Hook - Context Management Within Sessions

The `pre_compact_hook` in `client.py` fires when the Claude Code CLI triggers automatic compaction (context approaching limits). It provides custom instructions to the compaction summarizer:

**Preserve:**
- Current feature ID, name, status
- List of modified files with their purpose
- Last test/lint results (pass/fail + key errors)
- Current workflow step
- Dependency information
- Git operations performed
- MCP tool call results

**Discard:**
- Screenshot base64 data
- Long grep/find output
- Repeated file reads
- Verbose npm/pip install output
- Full lint output when passing

There's a commented-out future compaction control:
```python
# compaction_control={"enabled": True, "context_token_threshold": 80000}
```
This is not currently implemented in the SDK.

## ClaudeSDKClient Configuration

The client is constructed with these parameters in `client.py`:

```python
ClaudeSDKClient(
    options=ClaudeAgentOptions(
        model=model,                           # e.g., "claude-opus-4-6"
        cli_path=system_cli,                   # Path to system 'claude' CLI
        system_prompt="You are an expert...",   # Short system prompt
        setting_sources=["project"],            # Load CLAUDE.md, skills, commands
        max_buffer_size=10 * 1024 * 1024,       # 10MB for Playwright screenshots
        allowed_tools=allowed_tools,           # Agent-type-specific tool list
        mcp_servers=mcp_servers,               # Feature MCP server config
        hooks={...},                           # PreToolUse (bash security), PreCompact
        max_turns=max_turns,                   # 300 for coding/init, 100 for testing
        cwd=str(project_dir.resolve()),        # Working directory
        settings=str(settings_file.resolve()), # Security settings JSON path
        env=sdk_env,                           # API config overrides
        betas=[...],                           # ["context-1m-2025-08-07"] or []
    )
)
```

### Agent-Type-Specific Tool Lists

Each agent type gets a restricted set of MCP tools:
- **Coding**: Read/write/claim/mark features, skip, clear in-progress (12 tools)
- **Testing**: Read features, mark passing/failing only (8 tools)
- **Initializer**: Create features, add dependencies, read stats (8 tools)

All agent types share the same built-in tools: Read, Write, Edit, Glob, Grep, Bash, WebFetch, WebSearch.

### Security Configuration

Three layers:
1. **Sandbox**: OS-level bash isolation enabled
2. **Permissions**: File operations restricted to project directory via `./**` globs
3. **Bash hook**: `bash_security_hook` validates commands against hierarchical allowlist before execution

## Session Management

### Auto-Continue

After a successful session (`status == "continue"`):
1. Check for rate limit indicators in response text
2. If rate limited, parse retry-after time or use exponential backoff
3. Parse specific rate limit reset time (supports "resets at 3pm (America/New_York)" format)
4. Check if all features are complete -- exit if done
5. Exit if in single-feature, batch, or testing mode
6. Sleep for the delay: `await asyncio.sleep(delay_seconds)` (default: 3 seconds)

**Important:** In orchestrator mode (the normal path), each subprocess runs with `--max-iterations 1`, so auto-continue within `agent.py` effectively never triggers for coding/testing agents. The orchestrator manages session lifecycle externally via its polling loop (5-second interval).

### Rate Limit Handling

Three tiers:
- **Known retry-after**: Use the parsed value (clamped to max)
- **Unknown rate limit**: Exponential backoff via `calculate_rate_limit_backoff()`
- **Non-rate-limit errors**: Linear backoff via `calculate_error_backoff()`

Both counters (`rate_limit_retries`, `error_retries`) reset independently.

### Process Limits (Parallel Mode)

The orchestrator enforces strict bounds:
- `MAX_PARALLEL_AGENTS = 5` - Maximum concurrent coding agents
- `MAX_TOTAL_AGENTS = 10` - Hard limit on total agents (coding + testing)
- Testing agents are capped at `max_concurrency` (same as coding agents)
- Total process count never exceeds 11 Python processes (1 orchestrator + 5 coding + 5 testing)

## Key File References

| File | Key Areas |
|------|-----------|
| `autonomous_agent_demo.py` | CLI args (53-189), two execution paths (265-310) |
| `agent.py` | Session loop (137-434), auto-continue (280-414), rate limiting (381-399) |
| `client.py` | SDK client creation (452-497), tools (149-205), security (253-306), betas (480), PreCompact hook (376-446) |
| `prompts.py` | Prompt loading fallback (29-69), feature prompts (72-266) |
| `parallel_orchestrator.py` | Orchestrator lifecycle (140-230), subprocess spawning (827-892), polling loop (1056-1129) |
| `progress.py` | `has_features()` for init detection (29-59) |
