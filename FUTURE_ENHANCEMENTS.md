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

### 🟡 Streaming Visibility in Spec Chat
- Show activity during "Claude is thinking..." phase in spec/expand chat sessions
- Display tool calls (file reads, searches) as they happen
- Stream partial text response as it's generated
- Similar to how Claude Code shows activity during processing
- Helps users understand what's happening instead of staring at a blank "thinking" indicator
- Could show: files being read, tools being called, partial responses streaming in

### 🔴 New Project Onboarding Flow
- Add a help/onboarding popup when arriving at project screen after spec creation
- Quick overview: "Hit play to start agent, click cog for settings, etc."
- Explain what each button does for first-time users
- Could be dismissible with "Don't show again" option
- Reduce confusion about "what do I do now?" after spec creation

### 🔴 Settings UX Improvements
- **Default to project settings instead of app settings** - Users often modify app settings thinking they're changing project settings
- Consider separating project vs app settings more clearly in the UI
- Maybe two separate buttons/tabs: "Project Settings" and "App Settings"
- Visual distinction to make it obvious which scope you're editing
- Current settings button always opens app settings first, causing confusion

### 🟡 Dev Server Auto-Start Clarity
- Clarify whether dev server needs to be started manually or automatically
- Option in project settings: "Auto-start dev server when agent starts"
- Show tooltip explaining the dev server button's purpose
- Consider auto-starting dev server for web projects by default

---

## Agent & Orchestrator

### [DONE] Documentation Admin Agent (Haiku)
- Background agent using Claude Haiku (cheap/fast) for admin tasks
- Integrated into main agent infrastructure (same pattern as initializer/coding/testing)
- Responsibilities:
  - Keep CLAUDE.md and README.md up to date with code changes
  - Maintain CHANGELOG.md with feature additions/fixes
  - Sync documentation with actual behavior
  - Flag outdated documentation for review
- Each project gets its own agent (not shared)
- Uses Claude Code authentication (no separate API key needed)
- Usage: `python autonomous_agent_demo.py --project-dir /path/to/project --agent-type doc-admin --max-iterations 1`

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
