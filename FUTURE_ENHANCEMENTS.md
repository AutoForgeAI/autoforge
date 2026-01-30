# Future Enhancements

A running list of ideas and improvements to implement when time permits.

---

## Settings & Configuration

### Provider Selection in Settings UI
- Add "Provider" section to settings with options: `Anthropic API` / `Vertex AI` / `Ollama`
- Show relevant config fields based on selection
- Add "Test Connection" button to verify credentials
- Currently Vertex AI and Ollama are configured via `.env` file only

---

## UI/UX Improvements

*(Add ideas here)*

---

## Agent & Orchestrator

### 🟡 Documentation Admin Agent (Haiku)
- Background agent using Claude Haiku (cheap/fast) for admin tasks
- Responsibilities:
  - Keep CLAUDE.md and README.md up to date with code changes
  - Maintain CHANGELOG.md with feature additions/fixes
  - Update version documentation
  - Sync documentation with actual behavior
  - Flag outdated documentation for review
- Runs periodically or triggered by commits
- "Maestro's Admin Assistant" - handles the paperwork

---

## Testing & Quality

*(Add ideas here)*

---

## Documentation

*(Add ideas here)*

---

## Notes

- Priority: 🔴 High | 🟡 Medium | 🟢 Low
- Add `[DONE]` prefix when completed
- Move completed items to a "Completed" section at the bottom if desired
