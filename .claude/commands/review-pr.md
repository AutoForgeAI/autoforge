---
description: Review pull requests
---

Pull request(s): $ARGUMENTS

- If no PR numbers are provided, ask the user to provide PR number(s).
- At least 1 PR is required.

## TASKS

1. **Retrieve PR Details**
   - Use the GH CLI tool to retrieve the details (descriptions, diffs, comments, feedback, reviews, etc)

2. **Check for Merge Conflicts**
   - After retrieving PR details, check whether the PR has merge conflicts against the target branch
   - Use `gh pr view <number> --json mergeable,mergeStateStatus` or attempt a local merge check with `git merge-tree`
   - If conflicts exist, note the conflicting files — these must be resolved on the PR branch before merging
   - Surface conflicts early so they inform the rest of the review (don't discover them as a surprise at merge time)

3. **Assess PR Complexity**

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

4. **Analyze Codebase Impact**
   - Based on the complexity tier determined above, spawn the appropriate number of deep dive subagents
   - For Simple PRs: analyze directly without spawning agents
   - For Medium PRs: spawn 1-2 agents focusing on the most impacted areas
   - For Complex PRs: spawn up to 3 agents to cover security, performance, and architectural concerns

5. **PR Scope & Title Alignment Check**
   - Compare the PR title and description against the actual diff content
   - Check whether the PR is focused on a single coherent change or contains multiple unrelated changes
   - If the title/description describe one thing but the PR contains significantly more (e.g., title says "fix typo in README" but the diff touches 20 files across multiple domains), flag this as a **scope mismatch**
   - A scope mismatch is a **merge blocker** — recommend the author split the PR into smaller, focused PRs
   - Suggest specific ways to split the PR (e.g., "separate the refactor from the feature addition")
   - Reviewing large, unfocused PRs is impractical and error-prone; the review cannot provide adequate assurance for such changes

6. **Vision Alignment Check**
   - Read the project's README.md and CLAUDE.md to understand the application's core purpose
   - Assess whether this PR aligns with the application's intended functionality
   - If the changes deviate significantly from the core vision or add functionality that doesn't serve the application's purpose, note this in the review
   - This is not a blocker, but should be flagged for the reviewer's consideration

7. **Safety Assessment**
   - Provide a review on whether the PR is safe to merge as-is
   - Provide any feedback in terms of risk level

8. **Improvements**
   - Propose any improvements in terms of importance and complexity

9. **Merge Recommendation**
   - Based on all findings (including merge conflict status from step 2), provide a clear recommendation
   - **If no concerns and no conflicts**: recommend merging as-is
   - **If concerns are minor/fixable and/or merge conflicts exist**: recommend fixing on the PR branch first, then merging. Never merge a PR with known issues to main — always fix on the PR branch first
   - **If there are significant concerns** (bugs, security issues, architectural problems, scope mismatch) that require author input or are too risky to fix: recommend **not merging** and explain what needs to be resolved

10. **TLDR**
    - End the review with a `## TLDR` section
    - In 3-5 bullet points maximum, summarize:
      - What this PR is actually about (one sentence)
      - Merge conflict status (clean or conflicting files)
      - The key concerns, if any (or "no significant concerns")
      - **Verdict: MERGE** / **MERGE (after fixes)** / **DON'T MERGE** with a one-line reason
    - This section should be scannable in under 10 seconds

    Verdict definitions:
    - **MERGE** — no issues, clean to merge as-is
    - **MERGE (after fixes)** — minor issues and/or conflicts exist, but can be resolved on the PR branch first, then merged
    - **DON'T MERGE** — needs author attention, too complex or risky to fix without their input

11. **Post-Review Action**
    - Immediately after the TLDR, provide a `## Recommended Action` section
    - Based on the verdict, recommend one of the following actions:

    **If verdict is MERGE (no concerns):**
    - Merge as-is. No further action needed.

    **If verdict is MERGE (after fixes):**
    - List the specific changes that need to be made (fixes, conflict resolutions, etc.)
    - Offer to: check out the PR branch, resolve any merge conflicts, apply the minor fixes identified during review, push the updated branch, then merge the now-clean PR
    - Ask the user: *"Should I check out the PR branch, apply these fixes, and then merge?"*
    - **Never merge first and fix on main later** — always fix on the PR branch before merging

    **If verdict is DON'T MERGE:**
    - If the issues are contained and you are confident you can fix them: offer the same workflow as "MERGE (after fixes)" — check out the PR branch, apply fixes, push, then merge
    - If the issues are too complex, risky, or require author input (e.g., design decisions, major refactors, unclear intent): recommend sending the PR back to the author with specific feedback on what needs to change
    - Be honest about your confidence level — if you're unsure whether you can address the concerns correctly, say so and defer to the author