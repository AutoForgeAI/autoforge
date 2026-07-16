[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/autoforgeai-autoforge-badge.png)](https://mseep.ai/app/autoforgeai-autoforge)

# AutoForge

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/leonvanzyl)

A long-running autonomous coding agent powered by the Claude Agent SDK. This tool can build complete applications over multiple sessions using a two-agent pattern (initializer + coding agent). Includes a React-based UI for monitoring progress in real-time.

> [!WARNING]
> **Authentication:** Anthropic's policy states that third-party developers may not offer `claude.ai` login or subscription-based rate limits for their products (including agents built on the Claude Agent SDK) unless previously approved. Using your Claude subscription with AutoForge may risk account suspension. We recommend using an API key from [console.anthropic.com](https://console.anthropic.com/) instead.

> [!NOTE]
> **This repository is no longer actively maintained.** Most agent coding tools now ship their own long-running harnesses, making this project less necessary. Feel free to fork and continue development on your own!

## Video Tutorial

[![Watch the tutorial](https://img.youtube.com/vi/nKiPOxDpcJY/hqdefault.jpg)](https://youtu.be/nKiPOxDpcJY)

> **[Watch the setup and usage guide →](https://youtu.be/nKiPOxDpcJY)**

---

## Prerequisites

- **Node.js 20+** - Required for the CLI
- **Python 3.11+** - Auto-detected on first run ([download](https://www.python.org/downloads/))
- **Claude Code CLI** - Install and authenticate (see below)

### Claude Code CLI (Required)

**macOS / Linux:**
```bash
curl -fsSL https://claude.ai/install.sh | bash
```

**Windows (PowerShell):**
```powershell
irm https://claude.ai/install.ps1 | iex
```

### Authentication

You need one of the following:

- **Anthropic API Key** (recommended) - Pay-per-use from https://console.anthropic.com/
- **Claude Pro/Max Subscription** - Use `claude login` to authenticate (see warning above)

---

## Quick Start

### Option 1: npm Install (Recommended)

```bash
npm install -g autoforge-ai
autoforge
```

On first run, AutoForge automatically:
1. Checks for Python 3.11+
2. Creates a virtual environment at `~/.autoforge/venv/`
3. Installs Python dependencies
4. Copies a default config file to `~/.autoforge/.env`
5. Starts the server and opens your browser

### CLI Commands

```
autoforge                       Start the server (default)
autoforge config                Open ~/.autoforge/.env in $EDITOR
autoforge config --path         Print config file path
autoforge config --show         Show active configuration values
autoforge --port PORT           Custom port (default: auto from 8888)
autoforge --host HOST           Custom host (default: 127.0.0.1)
autoforge --no-browser          Don't auto-open browser
autoforge --repair              Delete and recreate virtual environment
autoforge --version             Print version
autoforge --help                Show help
```

### Option 2: From Source (Development)

Clone the repository and use the start scripts directly. This is the recommended path if you want to contribute or modify AutoForge itself.

```bash
git clone https://github.com/leonvanzyl/autoforge.git
cd autoforge
```

**Web UI:**

| Platform | Command |
|---|---|
| Windows | `start_ui.bat` |
| macOS / Linux | `./start_ui.sh` |

This launches the React-based web UI at `http://localhost:5173` with:
- Project selection and creation
- Kanban board view of features
- Real-time agent output streaming
- Start/pause/stop controls

**CLI Mode:**

| Platform | Command |
|---|---|
| Windows | `start.bat` |
| macOS / Linux | `./start.sh` |

The start script will:
1. Check if Claude CLI is installed
2. Check if you're authenticated (prompt to configure authentication if not)
3. Create a Python virtual environment
4. Install dependencies
5. Launch the main menu

### Creating or Continuing a Project

You'll see options to:
- **Create new project** - Start a fresh project with AI-assisted spec generation
- **Continue existing project** - Resume work on a previous project

For new projects, you can use the built-in `/create-spec` command to interactively create your app specification with Claude's help.

---

## How It Works

### Two-Agent Pattern

1. **Initializer Agent (First Session):** Reads your app specification, creates features in a SQLite database (`features.db`), sets up the project structure, and initializes git.

2. **Coding Agent (Subsequent Sessions):** Picks up where the previous session left off, implements features one by one, and marks them as passing in the database.

### Feature Management

Features are stored in SQLite via SQLAlchemy and managed through an MCP server that exposes tools to the agent:
- `feature_get_stats` - Progress statistics
- `feature_get_next` - Get highest-priority pending feature
- `feature_get_for_regression` - Random passing features for regression testing
- `feature_mark_passing` - Mark feature complete
- `feature_skip` - Move feature to end of queue
- `feature_create_bulk` - Initialize all features (used by initializer)

### Session Management

- Each session runs with a fresh context window
- Progress is persisted via SQLite database and git commits
- The agent auto-continues between sessions (3 second delay)
- Press `Ctrl+C` to pause; run the start script again to resume

---

## Important Timing Expectations

> **Note: Building complete applications takes time!**

- **First session (initialization):** The agent generates feature test cases. This takes several minutes and may appear to hang - this is normal.

- **Subsequent sessions:** Each coding iteration can take **5-15 minutes** depending on complexity.

- **Full app:** Building all features typically requires **many hours** of total runtime across multiple sessions.

**Tip:** The feature count in the prompts determines scope. For faster demos, you can modify your app spec to target fewer features (e.g., 20-50 features for a quick demo).

---

## Project Structure

```
autoforge/
├── bin/                         # npm CLI entry point
├── lib/                         # CLI bootstrap and setup logic
├── start.py                     # CLI menu and project management
├── start_ui.py                  # Web UI backend (FastAPI server launcher)
├── autonomous_agent_demo.py     # Agent entry point
├── agent.py                     # Agent session logic
├── client.py                    # Claude SDK client configuration
├── security.py                  # Bash command allowlist and validation
├── progress.py                  # Progress tracking utilities
├── prompts.py                   # Prompt loading utilities
├── api/
│   └── database.py              # SQLAlchemy models (Feature table)
├── mcp_server/
│   └── feature_mcp.py           # MCP server for feature management tools
├── server/
│   ├── main.py                  # FastAPI REST API server
│   ├── websocket.py             # WebSocket handler for real-time updates
│   ├── schemas.py               # Pydantic schemas
│   ├── routers/                 # API route handlers
│   └── services/                # Business logic services
├── ui/                          # React frontend
│   ├── src/
│   │   ├── App.tsx              # Main app component
│   │   ├── hooks/               # React Query and WebSocket hooks
│   │   └── lib/                 # API client and types
│   ├── package.json
│   └── vite.config.ts
├── .claude/
│   ├── commands/
│   │   └── create-spec.md       # /create-spec slash command
│   ├── skills/                  # Claude Code skills
│   └── templates/               # Prompt templates
├── requirements.txt             # Python dependencies (development)
├── requirements-prod.txt        # Python dependencies (npm install)
├── package.json                 # npm package definition
└── .env                         # Optional configuration
```

---

## Generated Project Structure

After the agent runs, your project directory will contain:

```
generations/my_project/
├── features.db               # SQLite database (feature test cases)
├── prompts/
│   ├── app_spec.txt          # Your app specification
│   ├── initializer_prompt.md # First session prompt
│   └── coding_prompt.md      # Continuation session prompt
├── init.sh                   # Environment setup script
├── claude-progress.txt       # Session progress notes
└── [application files]       # Generated application code
```

---

## Running the Generated Application

After the agent completes (or pauses), you can run the generated application:

```bash
cd generations/my_project

# Run the setup script created by the agent
./init.sh

# Or manually (typical for Node.js apps):
npm install
npm run dev
```

The application will typically be available at `http://localhost:3000` or similar.

---

## Security Model

This project uses a defense-in-depth security approach (see `security.py` and `client.py`):

1. **OS-level Sandbox:** Bash commands run in an isolated environment
2. **Filesystem Restrictions:** File operations restricted to the project directory only
3. **Bash Allowlist:** Only specific commands are permitted:
   - File inspection: `ls`, `cat`, `head`, `tail`, `wc`, `grep`
   - Node.js: `npm`, `node`
   - Version control: `git`
   - Process management: `ps`, `lsof`, `sleep`, `pkill` (dev processes only)

Commands not in the allowlist are blocked by the security hook.

---

## Web UI Development

The React UI is located in the `ui/` directory.

### Development Mode

```bash
cd ui
npm install
npm run dev      # Development server with hot reload
```

### Building for Production

```bash
cd ui
npm run build    # Builds to ui/dist/
```

**Note:** The `start_ui.bat`/`start_ui.sh` scripts serve the pre-built UI from `ui/dist/`. After making UI changes, run `npm run build` to see them when using the start scripts.

### Tech Stack

- React 18 with TypeScript
- TanStack Query for data fetching
- Tailwind CSS v4 with neobrutalism design
- Radix UI components
- WebSocket for real-time updates

### Real-time Updates

The UI receives live updates via WebSocket (`/ws/projects/{project_name}`):
- `progress` - Test pass counts
- `agent_status` - Running/paused/stopped/crashed
- `log` - Agent output lines (streamed from subprocess stdout)
- `feature_update` - Feature status changes

---

## Configuration

AutoForge reads configuration from a `.env` file. The file location depends on how you installed AutoForge:

| Install method | Config file location | Edit command |
|---|---|---|
| npm (global) | `~/.autoforge/.env` | `autoforge config` |
| From source | `.env` in the project root | Edit directly |

A default config file is created automatically on first run. Use `autoforge config` to open it in your editor, or `autoforge config --show` to print the active values.

### N8N Webhook Integration

Add to your `.env` to send progress notifications to an N8N webhook:

```bash
# Optional: N8N webhook for progress notifications
PROGRESS_N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-webhook-id
```

When test progress increases, the agent sends:

```json
{
  "event": "test_progress",
  "passing": 45,
  "total": 200,
  "percentage": 22.5,
  "project": "my_project",
  "timestamp": "2025-01-15T14:30:00.000Z"
}
```

### Alternative API Providers (GLM, Ollama, Kimi, Custom)

Alternative providers are configured via the **Settings UI** (gear icon > API Provider). Select your provider, set the base URL, auth token, and model directly in the UI — no `.env` changes needed.

Available providers: **Claude** (default), **GLM** (Zhipu AI), **Ollama** (local models), **Kimi** (Moonshot), **Custom**

For Ollama, install [Ollama v0.14.0+](https://ollama.com), run `ollama serve`, and pull a coding model (e.g., `ollama pull qwen3-coder`). Then select "Ollama" in the Settings UI.

### Using Vertex AI

Add these variables to your `.env` file to run agents via Google Cloud Vertex AI:

```bash
CLAUDE_CODE_USE_VERTEX=1
CLOUD_ML_REGION=us-east5
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project-id
ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-4-6
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-4-5@20250929
ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-3-5-haiku@20241022
```

Requires `gcloud auth application-default login` first. Note the `@` separator (not `-`) in Vertex AI model names.

---

## Customization

### Changing the Application

Use the `/create-spec` command when creating a new project, or manually edit the files in your project's `prompts/` directory:
- `app_spec.txt` - Your application specification
- `initializer_prompt.md` - Controls feature generation

### Modifying Allowed Commands

Edit `security.py` to add or remove commands from `ALLOWED_COMMANDS`.

---

## Troubleshooting

**"Claude CLI not found"**
Install the Claude Code CLI using the instructions in the Prerequisites section.

**"Not authenticated with Claude"**
Set your API key via `ANTHROPIC_API_KEY` environment variable or the Settings UI. Alternatively, run `claude login` to use subscription credentials, but note that Anthropic's policy may not permit subscription-based auth for third-party agents.

**"Appears to hang on first run"**
This is normal. The initializer agent is generating detailed test cases, which takes significant time. Watch for `[Tool: ...]` output to confirm the agent is working.

**"Command blocked by security hook"**
The agent tried to run a command not in the allowlist. This is the security system working as intended. If needed, add the command to `ALLOWED_COMMANDS` in `security.py`.

**"Python 3.11+ required but not found"**
Install Python 3.11 or later from [python.org](https://www.python.org/downloads/). Make sure `python3` (or `python` on Windows) is on your PATH.

**"Python venv module not available"**
On Debian/Ubuntu, the venv module is packaged separately. Install it with `sudo apt install python3.XX-venv` (replace `XX` with your Python minor version, e.g., `python3.12-venv`).

**"AutoForge is already running"**
A server instance is already active. Use the browser URL shown in the terminal, or stop the existing instance with Ctrl+C first.

**Virtual environment issues after a Python upgrade**
Run `autoforge --repair` to delete and recreate the virtual environment from scratch.

---

## License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE.md](LICENSE.md) file for details.
Copyright (C) 2026 Leon van Zyl (https://leonvanzyl.com)
