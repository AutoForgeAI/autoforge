---
allowed-tools: Read, Write, Bash, Glob, Grep
description: Convert GSD codebase mapping (.planning/codebase/*.md) into AutoCoder prompts/app_spec.txt
---

# GSD → AutoCoder Spec

If a project already has GSD/Claude codebase mapping docs under:

- `.planning/codebase/STACK.md`
- `.planning/codebase/ARCHITECTURE.md`
- `.planning/codebase/STRUCTURE.md`

You can convert them into AutoCoder’s `prompts/app_spec.txt` using the **Web UI**:

1. Open AutoCoder UI
2. Select the project
3. Settings → Generate → **GSD → app_spec.txt**

This uses the same multi-model generate pipeline (Codex/Gemini CLIs + optional synthesis) and writes:

- `prompts/app_spec.txt`
- Drafts under `.autocoder/drafts/spec/...`

