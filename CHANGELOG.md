# Changelog

All notable changes to this fork will be listed here.

## Unreleased

- Project setup required banner with 24h snooze (Expand stays locked until spec is real)
- Project reset endpoint (runtime reset + full reset) and UI Danger Zone controls
- Knowledge files (`/knowledge/*.md`) injected into prompts + UI editor modal
- Single-agent loop exits when no pending/staged/verification features remain
- Clarified prompt guidance: refactor/cleanup features are mandatory and override the original spec
- Regression selection now prioritizes least-tested features (tracks `regression_count`)
- UI auto-build now detects stale `ui/dist` and rebuilds when sources are newer
- WebSocket debug logs deduplicate consecutive identical lines (prevents StrictMode double-connect noise)
- Assistant chat: avoid history loss on conversation switch, disable input while loading, and reduce server log noise
- Scheduled runs (UI) with persisted schedule state
- New `AUTOCODER_STOP_WHEN_DONE` toggle to keep agents alive on empty queues
- LAN-ready UI host toggle (`AUTOCODER_UI_HOST`, `AUTOCODER_UI_ALLOW_REMOTE`)
- Windows CLI length guard for assistant chat via temporary `CLAUDE.md`

## 2026-01-17

- Web UI startup banner + boot checklist; auto-open browser toggle
- Windows terminal auto-install for pywinpty in UI
- Dynamic spec/expand skill resolution fixes
