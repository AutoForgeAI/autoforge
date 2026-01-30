---
description: Review pull requests
---

Pull request(s): $ARGUMENTS

- If no PR numbers are provided, ask the user to provide PR number(s).
- At least 1 PR is required.

## TASKS

1. **Retrieve PR Details**
   - Use the GH CLI tool to retrieve the details (descriptions, diffs, comments, feedback, reviews, etc)

2. **Assess PR Complexity**

   After retrieving PR details, assess complexity based on:
   - Number of files changed
   - Lines added/removed
   - Number of contributors/commits
   - Whether changes touch core/architectural files

   ### Complexity Tiers

   **Simple** (no deep dive agents needed):
   - ≤5 files changed AND ≤100 lines changed AND single author
   - Review directly without spawning agents

   **Medium** (1-2 deep dive agents):
   - 6-15 files changed, OR 100-500 lines, OR 2 contributors
   - Spawn 1 agent for focused areas, 2 if changes span multiple domains

   **Complex** (up to 3 deep dive agents):
   - >15 files, OR >500 lines, OR >2 contributors, OR touches core architecture
   - Spawn up to 3 agents to analyze different aspects (e.g., security, performance, architecture)

3. **Analyze Codebase Impact**
   - Based on the complexity tier determined above, spawn the appropriate number of deep dive subagents
   - For Simple PRs: analyze directly without spawning agents
   - For Medium PRs: spawn 1-2 agents focusing on the most impacted areas
   - For Complex PRs: spawn up to 3 agents to cover security, performance, and architectural concerns

4. **Vision Alignment Check**
   - Read the project's README.md and CLAUDE.md to understand the application's core purpose
   - Assess whether this PR aligns with the application's intended functionality
   - If the changes deviate significantly from the core vision or add functionality that doesn't serve the application's purpose, note this in the review
   - This is not a blocker, but should be flagged for the reviewer's consideration

5. **Safety Assessment**
   - Provide a review on whether the PR is safe to merge as-is
   - Provide any feedback in terms of risk level

6. **Improvements**
   - Propose any improvements in terms of importance and complexity