---
description: Review pull requests
---

Pull request(s): $ARGUMENTS

- If no PR numbers are provided, ask the user to provide PR number(s).
- At least 1 PR is required.

## TASKS
- Use the GH CLI tool to retrieve the details (descriptions, divs, comments, feedback, reviews, etc)
- Use 3 deepdive subagents to analyze the impact of the codebase
- Provide a review on whether the PR is safe to merge as-is
- Provide any feedback in terms of risk level
- Propose any improments in terms of importance and complexity 