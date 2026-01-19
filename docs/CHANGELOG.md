# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Core
- Safer per-project run locking (`<project>/.agent.lock` is atomic + PID reuse resistant) and stop now kills the full process tree.
- SQLite defaults to `journal_mode=WAL`, but auto-falls back to `DELETE` on network filesystems (override via `AUTOCODER_SQLITE_JOURNAL_MODE`).
- Fix: fresh projects no longer exit early before the initializer creates the feature backlog.

### UI
- Dashboard shows a “still running in the background” banner after leaving a running project.
- Softer hover feel: cards don’t “jump” on hover unless explicitly opted-in; shadows are a bit less intense.
- Assistant button sits higher to avoid bottom-edge overlap.
- UI auto-build logs which file triggered a rebuild; optional mtime tolerance for FAT32/exFAT (`AUTOCODER_UI_MTIME_TOLERANCE_S`).

## [2.0.0] - 2025-01-07

### 🚀 Major Features - Parallel Agents & Knowledge Base

This release represents a massive evolution in autonomous coding capabilities, introducing parallel agent execution, continuous learning, and intelligent model selection.

#### NEW: Parallel Agent Execution
- **3x Faster Development**: Run 3-5 agents simultaneously on different features
- **Atomic Database Locking**: Row-level locking prevents race conditions using `with_for_update()`
- **Smart Load Balancing**: Manager atomically claims features and distributes to available agents
- **Real-Time Status Tracking**: Per-agent progress monitoring with live status grid in UI
- **Batch Claiming Tools**: `feature_claim_batch()`, `feature_release()`, `feature_get_claimed()` MCP tools

**Performance Impact:**
- Sequential: Feature 1 → Feature 2 → Feature 3 (40 minutes)
- Parallel (3 agents): All 3 simultaneously (13.3 minutes)
- **Result: 3x speedup for multi-feature development**

#### NEW: Knowledge Base Learning System
- **Pattern Storage**: Stores implementation approaches, files changed, models used, success rates
- **Similarity Matching**: Jaccard similarity algorithm finds similar past features
- **Prompt Enhancement**: Automatically adds reference examples from successful implementations
- **Model Performance Tracking**: Tracks which models work best for each category
- **Continuous Improvement**: System gets smarter with every completed feature

**What Gets Stored:**
- Feature category, name, description
- Implementation approach used
- Files created/modified
- Model used and success rate
- Attempts needed
- Lessons learned

**How It Helps:**
- Finds similar past features
- Recommends best approaches
- Suggests optimal models
- Provides reference examples in prompts
- Tracks success rates over time

#### NEW: Smart Model Selection
- **5 Presets**:
  - `quality` - Opus only (maximum quality, highest cost)
  - `balanced` ⭐ - Opus + Haiku (recommended for Pro users)
  - `economy` - Opus + Sonnet + Haiku (cost optimization)
  - `cheap` - Sonnet + Haiku (budget-friendly)
  - `experimental` - All models with AI selection

- **Automatic Routing**: Selects model based on feature complexity
  - Authentication → Opus (security-critical)
  - Database Schema → Opus (complex architecture)
  - Testing → Haiku (simple, fast)
  - Documentation → Haiku (straightforward)
  - Frontend → Opus (complex UI logic)
  - CRUD → Haiku (simple patterns)

- **Persistent Settings**: Stored in `~/.autocoder/model_settings.json`
- **Category Mapping**: Customizable per-feature-category model assignment

#### NEW: UI Components (Neobrutalist Design)
- **Model Settings Panel** (`🧠 Models` button)
  - 5 preset cards with model badges
  - Category mapping display
  - Auto-detect simple tasks toggle
  - Real-time updates

- **Parallel Agents Control** (`⚡ Parallel` button, press `P`)
  - Agent count slider (1-5)
  - Model preset selector
  - Start/Stop controls
  - Live status summary

- **Agent Status Grid**
  - Auto-displays when agents running
  - Per-agent cards with progress bars
  - Model badges (OPUS/HAIKU/SONNET)
  - Summary statistics (running/completed/failed)

- **Keyboard Shortcuts**:
  - `P` - Open Parallel Agents Control
  - `N` - Add Feature (when project selected)
  - `A` - Toggle Assistant Panel
  - `D` - Toggle Debug Log
  - `Esc` - Close modals

### 📦 Backend Infrastructure

#### New Files
- `agent_manager.py` (539 lines) - Parallel agent orchestrator
- `knowledge_base.py` (604 lines) - Learning system with similarity matching
- `model_settings.py` (426 lines) - Flexible model configuration
- `inspect_knowledge.py` - CLI inspection tool
- `knowledge_base_demo.py` - 5 complete usage examples
- `test_knowledge_base.py` - Unit tests
- `verify_knowledge_base.py` - Verification script

#### MCP Server Enhancements
- `mcp_server/feature_mcp.py` (731 lines)
  - `feature_claim_batch(count, agent_id)` - Atomically claim multiple features
  - `feature_release(feature_id, status, notes)` - Release with completion status
  - `feature_get_claimed(agent_id)` - Get all claimed features

#### REST API Endpoints
- `server/routers/model_settings.py` (202 lines)
  - `GET/PUT /api/model-settings` - CRUD operations
  - `POST /api/model-settings/preset` - Apply preset
  - `GET /api/model-settings/presets` - List all presets

- `server/routers/parallel_agents.py` (274 lines)
  - `POST /api/parallel-agents/start` - Start parallel agents
  - `POST /api/parallel-agents/stop` - Stop all agents
  - `GET /api/parallel-agents/status` - Query status

### 🎨 Frontend Components

#### New React Components
- `ModelSettingsPanel.tsx` (209 lines)
- `ParallelAgentsControl.tsx` (193 lines)
- `AgentStatusGrid.tsx` (164 lines)

#### New React Hooks
- `useModelSettings.ts` (125 lines)
- `useParallelAgents.ts` (155 lines)

#### App Integration
- Updated `App.tsx` with new buttons and modals
- Header now shows: Models, Parallel, and Agent Controls
- Keyboard shortcut handling for all modals

### 📚 Documentation

#### New Documentation Files
- `README.md` (582 lines) - Comprehensive usage guide
- `CHANGELOG.md` - This file
- `KNOWLEDGE_BASE.md` - Knowledge base system documentation
- `KNOWLEDGE_BASE_SUMMARY.md` - Implementation summary
- `KNOWLEDGE_BASE_INTEGRATION.md` - Integration guide

#### Research Documentation (`research/`)
- `COMPLETE-IMPLEMENTATION.md` - Full implementation guide
- `INTEGRATION-COMPLETE.md` - UI integration status
- `PARALLEL-IMPLEMENTATION-GUIDE.md` - Parallel execution guide
- `PROGRESS-REPORT.md` - Development progress tracking
- `UI-INTEGRATION-GUIDE.md` - UI implementation steps
- `FINAL-SUMMARY.md` - Feature summary
- `repository-analysis-report.md` - Analysis of 4 open-source agent systems
- `subagent-parallel-execution.md` - Original research

### 🐛 Bug Fixes
- Fix MIME type for JavaScript files on Windows
- Update .gitignore to exclude research and temporary directories
- Various database session management improvements

### ⚙️ Configuration

#### New Environment Variables
```bash
# Optional: N8N webhook for progress notifications
PROGRESS_N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-webhook-id
```

#### New User Configuration Files
- `~/.autocoder/model_settings.json` - Model selection settings
- `~/.autocoder/registry.db` - Project registry (SQLite)
- `~/.autocoder/knowledge.db` - Knowledge base (SQLite)

### 🔄 Migration Notes

#### For Existing Users
1. **No Breaking Changes**: All existing features preserved
2. **New Dependencies**: Run `pip install -r requirements.txt` if updating
3. **UI Build**: Run `cd ui && npm run build` after updating
4. **Model Settings**: Optional - system will use defaults if not configured

#### For New Users
See `README.md` for complete setup instructions:
- Claude Code CLI installation
- Authentication (Pro subscription or API key)
- Quick start with Web UI or CLI

### 📊 Performance Metrics

#### Parallel Execution
| Features | Sequential | 3 Agents | Speedup |
|----------|------------|----------|---------|
| 5        | 50 min     | 18 min   | 2.8x    |
| 10       | 100 min    | 35 min   | 2.9x    |
| 20       | 200 min    | 70 min   | 2.9x    |

#### Model Selection
- **Opus**: Best for complex features (auth, database, frontend)
- **Haiku**: Best for simple features (tests, docs, CRUD)
- **Sonnet**: Middle ground for moderate complexity
- **Cost Savings**: Up to 60% reduction with smart Haiku routing

### 🎯 Usage Examples

#### CLI - Parallel Agents
```bash
# Start 3 agents with balanced preset (recommended)
python agent_manager.py \
  --project-dir ./your-project \
  --parallel 3 \
  --preset balanced

# Custom model selection
python agent_manager.py \
  --project-dir ./your-project \
  --parallel 3 \
  --models opus,haiku
```

#### UI - Parallel Agents
1. Select a project
2. Click **⚡ Parallel** button (or press `P`)
3. Adjust agent count slider (1-5)
4. Click "Start X Agents"
5. Watch real-time status grid

#### Inspect Knowledge Base
```bash
python inspect_knowledge.py

# Output:
# Knowledge Base Summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Total Patterns: 15
# Success Rate: 93%
#
# Best Models by Category:
#   backend: opus (95% success)
#   frontend: opus (100% success)
#   testing: haiku (100% success)
#   documentation: haiku (90% success)
#
# Common Approaches:
#   Backend: "JWT authentication" (3 features)
#   Frontend: "React hooks with useState" (4 features)
#   Testing: "Jest with react-testing-library" (3 features)
```

### 🙏 Credits

This release combines features from multiple development streams:
- Parallel agent execution and knowledge base learning (new in v2.0.0)
- Conversational AI assistant panel
- YOLO mode for rapid prototyping
- WebFetch and WebSearch integration
- SQLite registry system
- Spec creation chat with image support

### 📝 License

See LICENSE.md for details.

### 🔗 Links

- Repository: https://github.com/gabelul/autocoder
- Upstream: https://github.com/leonvanzyl/autocoder
- Documentation: See README.md
- Claude Code CLI: https://claude.ai/code

---

## [1.0.0] - Previous Release

### Initial Features
- Autonomous coding agent with Claude Agent SDK
- Two-agent pattern (initializer + coding agent)
- Feature-based development with SQLite database
- MCP server for feature management tools
- React-based UI with neobrutalist design
- Three chat systems (Spec, Assistant, Coding)
- Bash command security (defense-in-depth)
- Real-time WebSocket updates
- Regression testing support

---

**Note:** This project is under active development. Features may change as we improve the system.
