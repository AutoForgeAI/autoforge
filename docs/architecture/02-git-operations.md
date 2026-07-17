# Git Operations & Implicit Commits

## Overview

AutoForge **never** executes git commands programmatically from its Python/Node.js backend code. All git operations are performed by the Claude AI agent through prompt template instructions. These are "implicit" commits -- they happen automatically because the agent follows its workflow instructions, not because AutoForge code runs `git commit`.

## When Git Commits Happen

### 1. Initializer Agent - Project Setup (First Session)

**Source:** `.claude/templates/initializer_prompt.template.md`

The initializer agent is instructed to:

**First Commit (THIRD TASK - Initialize Git):**
```
Create a git repository and make your first commit with:
- init.sh (environment setup script)
- README.md (project overview and setup instructions)
- Any initial project structure files

Commit message: "Initial setup: init.sh, project structure, and features created via API"
```

**Second Commit (Before ending session):**
```
1. Commit all work with a descriptive message
2. Verify features were created using the feature_get_stats tool
3. Leave the environment in a clean, working state
```

Result: The initializer creates **1-2 commits** per project initialization.

### 2. Coding Agent - Per-Feature Commits

**Source:** `.claude/templates/coding_prompt.template.md`

**Per-feature commit (STEP 7: COMMIT YOUR PROGRESS):**
```bash
git add .
git commit -m "Implement [feature name] - verified end-to-end"
# Or:
git add .
git commit -m "feat: implement [feature name] with browser verification"
```

**Git Commit Rules from the prompt:**
- ALWAYS use simple `-m` flag for commit messages
- NEVER use heredocs (they fail in sandbox mode)
- For multi-line messages, use multiple `-m` flags

**End-of-session commit (STEP 9: END SESSION CLEANLY):**
```
1. Commit all working code
2. Update claude-progress.txt
3. Mark features as passing if tests verified
4. Ensure no uncommitted changes
5. Leave app in working state
```

**Reading git history (STEP 1):**
The coding agent is instructed to read recent history at the start of every session:
```bash
git log --oneline -20
```

Result: Each coding session produces **1-2 commits** (feature implementation + session cleanup).

### 3. Testing Agent - Regression Fix Commits

**Source:** `.claude/templates/testing_prompt.template.md`

When a regression is found and fixed:
```bash
git add .
git commit -m "Fix regression in [feature name]

- [Describe what was broken]
- [Describe the fix]
- Verified with browser automation"
```

The testing agent also uses `git log` for investigation:
```
Examine recent git commits that might have caused the regression
```

Result: Testing agents commit **only when regressions are found and fixed** (0-1 commits per session).

### 4. User-Invoked Slash Commands

**`/checkpoint` command** (`.claude/commands/checkpoint.md`):
- Runs `git init` if needed
- Runs `git status`, `git diff`, `git log -5 --oneline`
- Stages with `git add -A` or `git add .`
- Creates a detailed commit with co-author attribution
- This is **user-invoked only**, not automatic

**`/review-pr` command** (`.claude/commands/review-pr.md`):
- Uses `git merge-tree` for merge conflict checking
- Read-only git usage for PR analysis

## Git Pushes

**AutoForge never instructs the agent to push to a remote.**

- No `git push` appears in any template file
- No `git push` appears in any Python code
- No `git push` appears in any shell script

However, because `git` is in the security allowlist without subcommand restrictions, the agent **could** run `git push` if it decided to on its own. Nothing in the prompts instructs it to do so, and nothing in the security layer prevents it.

## Git in the Security Model

**Source:** `security.py`

`git` is allowed as a single entry in `ALLOWED_COMMANDS`:
```python
ALLOWED_COMMANDS = {
    # Version control
    "git",
    ...
}
```

Key implications:
- The security hook validates at the **command name level**, not the subcommand level
- All git subcommands are equally permitted: `commit`, `push`, `reset --hard`, `push --force`, etc.
- `git` is NOT in `COMMANDS_NEEDING_EXTRA_VALIDATION` (unlike `pkill`, `chmod`, `init.sh`, `playwright-cli`)
- `git` can be blocked org-wide by adding it to `blocked_commands` in `~/.autoforge/config.yaml`

## Git Initialization

AutoForge does **not** programmatically run `git init`. Instead:
1. The **initializer agent prompt** instructs the AI to create a git repository as its "THIRD TASK"
2. The **`/checkpoint` slash command** runs `git init` if needed (user-invoked only)

## Programmatic `.gitignore` Management

While AutoForge never runs git commands from code, it does manage `.gitignore` files:

### `.autoforge/.gitignore` (runtime files)

Created by `autoforge_paths.py` via `ensure_autoforge_dir()`:
```
# AutoForge runtime files
features.db
features.db-wal
features.db-shm
assistant.db
assistant.db-wal
assistant.db-shm
.agent.lock
.devserver.lock
.pause_drain
.claude_settings.json
.claude_assistant_settings.json
.claude_settings.expand.*.json
.progress_cache
.migration_version
```

### Project root `.gitignore` (Playwright artifacts)

Updated by `prompts.py` `scaffold_project_prompts()`:
- Appends `.playwright-cli/` and `.playwright/` entries
- Only adds entries that don't already exist
- Same logic runs during project migration

## Commit Timeline Diagram

```
Project Lifecycle:
═══════════════════════════════════════════════════════════════════

Session 1 (Initializer):
  git init
  ├── Commit: "Initial setup: init.sh, project structure, and features created via API"
  └── Commit: "Complete initialization with all features defined"

Session 2 (Coding Agent - Feature #1):
  git log --oneline -20  (reads history)
  ├── Implement feature
  ├── Commit: "feat: implement user authentication with browser verification"
  └── Commit: "Update progress notes" (if needed)

Session 3 (Coding Agent - Feature #2):
  git log --oneline -20  (reads history)
  ├── Implement feature
  └── Commit: "feat: implement dashboard layout with real data"

Session 4 (Testing Agent):
  git log (investigate regressions)
  ├── Find regression in Feature #1
  ├── Fix regression
  └── Commit: "Fix regression in user authentication - session handling"

... (repeats until all features pass)
```

## Summary Table

| Operation | Where | Mechanism | Frequency |
|-----------|-------|-----------|-----------|
| `git init` | initializer_prompt.template.md | Agent prompt instruction | Once per project |
| `git log --oneline -20` | coding_prompt.template.md | Agent prompt instruction | Every coding session |
| `git add . && git commit` | coding_prompt.template.md (STEP 7) | Agent prompt instruction | Every feature completion |
| `git add . && git commit` | coding_prompt.template.md (STEP 9) | Agent prompt instruction | Every session end |
| `git add . && git commit` | testing_prompt.template.md | Agent prompt instruction | Every regression fix |
| `git add . && git commit` | initializer_prompt.template.md | Agent prompt instruction | 1-2x during init |
| `git init` (if needed) | checkpoint.md | User slash command | On demand |
| `git add -A && git commit` | checkpoint.md | User slash command | On demand |
| `git merge-tree` | review-pr.md | User slash command | On demand |
| `.gitignore` write | autoforge_paths.py | Python `Path.write_text()` | Project setup |
| `.gitignore` append | prompts.py | Python file append | Project setup/migration |
| `git` allowed | security.py | Allowlist entry | Always active |

## Considerations for Parallel Mode

When running with multiple concurrent agents, all agents commit to the **same git repository** simultaneously. The prompt templates do not address git coordination between parallel agents. In practice:

- Each agent works on different files (different features)
- `git add . && git commit` could stage files from another agent's work
- Git's own locking mechanism (`.git/index.lock`) prevents simultaneous writes
- Merge conflicts are unlikely but possible if two features modify the same file

The orchestrator does not implement any git locking or sequential commit coordination.
