# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added
- **Documentation Admin Agent** - Background agent (Claude Haiku) that automatically keeps CLAUDE.md, README.md, and CHANGELOG.md in sync with code changes after project initialization
- **Lock file protection** - Documentation admin agent now checks for lock files to prevent duplicate runs
- **Timeout and CLI checks** - Assistant chat session now validates Claude CLI availability and handles timeouts gracefully

### Changed
- **UI improvements** - Enhanced task form layout and updated doc admin button styling
- **Doc admin triggering** - Integrated doc-admin agent into orchestrator pipeline to run automatically after project initialization
- **Model selection** - Doc admin now uses latest Haiku model for cost efficiency

### Fixed
- **API timeout handling** - Better error handling for assistant chat sessions with CLI validation
- **Browser popup issue** - Fixed unwanted popup behavior in browser testing mode
- **YOLO mode prompt** - Properly applies yolo_mode flag to disable browser testing in agent prompts

---

## [Previous Releases]

### Infrastructure
- Parallel orchestrator with dependency-aware scheduling
- Multi-agent execution support (up to 5 concurrent coding agents)
- Graceful shutdown and pause/resume controls
- Vertex AI model support integration
- Settings persistence with autoResume and pauseOnError options

### Security
- OS-level bash command sandboxing
- Filesystem restrictions to project directory
- Hierarchical command allowlist system (org, project, global levels)
- Extra read paths for cross-project file access with validation
- Sensitive directory blocklist for credentials protection

### UI/UX
- React 19 with TypeScript
- Kanban board view with 4 columns (Pending, In Progress, Testing, Done)
- Dependency graph visualization with dagre layout
- Real-time WebSocket updates for agent status and progress
- Agent Mission Control dashboard with mascots (Spark, Fizz, Octo, Hoot, Buzz)
- Settings panel with provider configuration options
- Debug panel for development

### Testing & Quality
- Security unit tests (12 tests)
- Security integration tests (9 tests)
- Playwright end-to-end tests for UI
- Linting with ruff (line length 120, Python 3.11)
- Type checking with mypy (strict mode)

### Documentation
- Comprehensive CLAUDE.md with architecture and security details
- README.md with quick start and configuration guides
- CUSTOM_UPDATES.md tracking customizations from upstream
- FUTURE_ENHANCEMENTS.md for planned improvements
- PHASE3_SPEC.md for mid-session approval feature specification

---

## [1.0.0] - Initial Release

### Added
- Autonomous coding agent using Claude Agent SDK
- Two-agent pattern: Initializer + Coding agents
- Feature management with SQLAlchemy ORM and SQLite
- MCP server for feature tools
- FastAPI REST API server
- React-based Web UI with real-time updates
- Project registry with cross-platform support
- Bash command security system
- Support for Ollama local models
- Support for Zhipu GLM models
- N8N webhook integration for progress notifications
- Interactive spec creation with `/create-spec` command

---

*For more details on specific changes, see the [git commit history](https://github.com/leonvanzyl/autocoder/commits).*
