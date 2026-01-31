"""
Documentation Admin Agent
=========================

A lightweight background agent that keeps project documentation in sync.
Uses Claude Haiku for cost-effective documentation maintenance.

Responsibilities:
- Assess documentation state on first run
- Keep CHANGELOG.md updated with changes
- Sync README.md and CLAUDE.md with code behavior
- Maintain a running log of all changes
- Flag outdated documentation

Each project gets its own doc admin agent (not shared).

Usage:
    # Run assessment for a project
    python doc_admin_agent.py --project-dir /path/to/project --assess

    # Run update cycle
    python doc_admin_agent.py --project-dir /path/to/project --update

    # Watch mode (run on file changes)
    python doc_admin_agent.py --project-dir /path/to/project --watch
"""

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

# Log file for tracking all documentation changes
DOC_ADMIN_LOG = ".doc_admin_log.jsonl"

# Files the doc admin manages
MANAGED_DOCS = [
    "README.md",
    "CLAUDE.md",
    "CHANGELOG.md",
    "FUTURE_ENHANCEMENTS.md",
    "docs/**/*.md",
]

# Doc admin prompt - tells the agent what to do
DOC_ADMIN_SYSTEM_PROMPT = """You are a Documentation Admin Agent - Maestro's assistant for keeping docs in sync.

Your responsibilities:
1. Assess documentation health and identify issues
2. Keep CHANGELOG.md updated with recent commits
3. Sync README.md and CLAUDE.md with actual code behavior
4. Flag outdated documentation

When assessing, provide structured feedback in JSON format.
When updating docs, make precise edits - don't rewrite entire files unnecessarily.
Focus on accuracy and keeping documentation in sync with the codebase.
"""


class DocAdminAgent:
    """Documentation Admin Agent - Maestro's assistant for keeping docs in sync."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.log_file = project_dir / DOC_ADMIN_LOG

    def log_change(self, action: str, details: dict):
        """Append a change record to the running log."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            **details,
        }
        with open(self.log_file, "a") as f:
            f.write(json.dumps(record) + "\n")
        print(f"[DocAdmin] Logged: {action}")

    def get_change_history(self, limit: int = 50) -> list[dict]:
        """Read recent changes from the log."""
        if not self.log_file.exists():
            return []

        records = []
        with open(self.log_file, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))

        return records[-limit:]

    def _gather_context(self) -> str:
        """Gather current state of documentation and recent code changes."""
        context_parts = []

        # Get recent git commits
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-20"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                context_parts.append(f"## Recent Commits\n```\n{result.stdout}\n```")
        except Exception:
            pass

        # Get current documentation files
        for pattern in ["README.md", "CLAUDE.md", "CHANGELOG.md", "FUTURE_ENHANCEMENTS.md"]:
            doc_path = self.project_dir / pattern
            if doc_path.exists():
                content = doc_path.read_text()[:5000]  # First 5k chars
                context_parts.append(f"## {pattern}\n```markdown\n{content}\n```")

        # Get change history
        history = self.get_change_history(10)
        if history:
            context_parts.append(
                f"## Recent Doc Admin Changes\n```json\n{json.dumps(history, indent=2)}\n```"
            )

        return "\n\n".join(context_parts)

    def _create_client(self, model: str = "haiku") -> ClaudeSDKClient:
        """Create a Claude SDK client for the doc admin agent."""
        options = ClaudeAgentOptions(
            model=model,
            cwd=str(self.project_dir),
            system_prompt=DOC_ADMIN_SYSTEM_PROMPT,
            allowed_tools=["Read", "Edit", "Write", "Glob", "Grep", "Bash"],
            permission_mode="acceptEdits",  # Auto-accept doc edits
        )
        return ClaudeSDKClient(options)

    async def _run_prompt(self, prompt: str, model: str = "haiku") -> str:
        """Run a prompt through the Claude SDK and return the response."""
        client = self._create_client(model)

        response_text = ""
        try:
            await client.query(prompt)

            async for msg in client.receive_response():
                msg_type = type(msg).__name__
                if msg_type == "AssistantMessage" and hasattr(msg, "content"):
                    for block in msg.content:
                        block_type = type(block).__name__
                        if block_type == "TextBlock" and hasattr(block, "text"):
                            response_text += block.text
                            print(block.text, end="", flush=True)
                        elif block_type == "ToolUseBlock" and hasattr(block, "name"):
                            print(f"\n[Tool: {block.name}]", flush=True)

            print()  # Newline after response
        finally:
            await client.close()

        return response_text

    async def assess(self) -> dict:
        """
        Run a thorough assessment of documentation state.
        Called on first run or when requested.
        """
        print(f"[DocAdmin] Running assessment for {self.project_dir.name}...")

        context = self._gather_context()

        prompt = f"""Assess the current state of documentation for this project.

{context}

Please provide a thorough assessment in JSON format:
{{
    "overall_health": "good|needs_attention|critical",
    "issues": [
        {{"file": "filename", "issue": "description", "priority": "high|medium|low"}}
    ],
    "missing_docs": ["list of documentation that should exist but doesn't"],
    "outdated_sections": ["list of sections that appear outdated based on recent commits"],
    "recommendations": ["list of recommended actions"],
    "summary": "brief overall summary"
}}

Be specific and actionable. Focus on documentation accuracy and completeness."""

        response_text = await self._run_prompt(prompt)

        # Try to extract JSON from response
        try:
            import re

            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if json_match:
                assessment = json.loads(json_match.group())
            else:
                assessment = {"raw_response": response_text}
        except json.JSONDecodeError:
            assessment = {"raw_response": response_text}

        # Log the assessment
        self.log_change(
            "assessment",
            {
                "result": assessment.get("overall_health", "unknown"),
                "issues_count": len(assessment.get("issues", [])),
            },
        )

        return assessment

    async def update_changelog(self) -> bool:
        """Update CHANGELOG.md with recent changes."""
        print("[DocAdmin] Updating CHANGELOG.md...")

        # Get commits since last update
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-30"],
                cwd=self.project_dir,
                capture_output=True,
                text=True,
            )
            commits = result.stdout if result.returncode == 0 else ""
        except Exception:
            commits = ""

        if not commits.strip():
            print("[DocAdmin] No new commits to document")
            return False

        # Read current changelog
        changelog_path = self.project_dir / "CHANGELOG.md"
        current_changelog = ""
        if changelog_path.exists():
            current_changelog = changelog_path.read_text()

        prompt = f"""Update the CHANGELOG.md file based on recent commits.

Recent commits:
```
{commits}
```

Current CHANGELOG.md:
```markdown
{current_changelog[:3000]}
```

Tasks:
1. Read the current CHANGELOG.md
2. Add a new section for today's date if there are meaningful changes
3. Group changes by type (Added, Changed, Fixed, etc.)
4. Keep the existing history intact
5. Use Keep a Changelog format (https://keepachangelog.com/)
6. Use the Edit tool to update the file

Only add entries for commits that represent meaningful user-facing changes."""

        await self._run_prompt(prompt)

        # Check if changelog was updated
        if changelog_path.exists():
            new_content = changelog_path.read_text()
            if new_content != current_changelog:
                self.log_change(
                    "update_changelog",
                    {"commits_processed": len(commits.strip().split("\n"))},
                )
                print("[DocAdmin] CHANGELOG.md updated")
                return True

        return False

    async def sync_docs(self) -> dict:
        """
        Sync documentation with current code state.
        Returns dict of files updated.
        """
        print("[DocAdmin] Syncing documentation...")

        updated = {}
        context = self._gather_context()

        # Check each managed doc
        for doc_name in ["README.md", "CLAUDE.md"]:
            doc_path = self.project_dir / doc_name
            if not doc_path.exists():
                continue

            current_content = doc_path.read_text()

            prompt = f"""Review {doc_name} for accuracy and update if needed.

Recent project context:
{context[:3000]}

Tasks:
1. Read the current {doc_name}
2. Check if it accurately reflects the current state of the project
3. If updates are needed, use the Edit tool to make precise corrections
4. Focus on:
   - Accuracy of described features and behavior
   - Correct command examples
   - Up-to-date configuration options

Only make changes if something is actually incorrect or outdated.
If no changes needed, just say "No updates needed for {doc_name}"."""

            await self._run_prompt(prompt)

            # Check if file was updated
            if doc_path.exists():
                new_content = doc_path.read_text()
                if new_content != current_content:
                    updated[doc_name] = True
                    self.log_change("sync_doc", {"file": doc_name})
                    print(f"[DocAdmin] Updated {doc_name}")

        return updated

    async def run_cycle(self, full_assessment: bool = False):
        """Run a complete documentation maintenance cycle."""
        print(f"\n{'=' * 60}")
        print(f"  DOC ADMIN AGENT - {self.project_dir.name}")
        print("  Using Claude Code authentication")
        print(f"{'=' * 60}\n")

        results = {
            "timestamp": datetime.now().isoformat(),
            "project": str(self.project_dir),
        }

        # Assessment (always on first run, optional otherwise)
        if full_assessment or not self.log_file.exists():
            results["assessment"] = await self.assess()
            print(f"\nAssessment: {results['assessment'].get('overall_health', 'unknown')}")
            if results["assessment"].get("issues"):
                print(f"Issues found: {len(results['assessment']['issues'])}")
                for issue in results["assessment"]["issues"][:5]:
                    print(
                        f"  - [{issue.get('priority', '?')}] {issue.get('file', '?')}: {issue.get('issue', '?')}"
                    )

        # Update changelog
        results["changelog_updated"] = await self.update_changelog()

        # Sync docs
        results["docs_synced"] = await self.sync_docs()

        print("\n[DocAdmin] Cycle complete")
        return results


async def main():
    parser = argparse.ArgumentParser(description="Documentation Admin Agent")
    parser.add_argument("--project-dir", required=True, help="Project directory path")
    parser.add_argument("--assess", action="store_true", help="Run full assessment")
    parser.add_argument("--update", action="store_true", help="Run update cycle")
    parser.add_argument("--changelog", action="store_true", help="Update changelog only")
    parser.add_argument("--sync", action="store_true", help="Sync docs only")
    parser.add_argument(
        "--watch", action="store_true", help="Watch mode (not implemented yet)"
    )

    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}")
        sys.exit(1)

    agent = DocAdminAgent(project_dir)

    if args.assess:
        result = await agent.assess()
        print(json.dumps(result, indent=2))
    elif args.changelog:
        await agent.update_changelog()
    elif args.sync:
        await agent.sync_docs()
    elif args.update or not any([args.assess, args.changelog, args.sync, args.watch]):
        # Default: run full cycle
        await agent.run_cycle(full_assessment=args.assess)
    elif args.watch:
        print("Watch mode not implemented yet - coming soon!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
