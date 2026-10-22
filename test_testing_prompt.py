"""
Testing Agent Prompt Tests
==========================

Tests for web-UI detection and the command-line verification strategy
used by testing agents on projects without a web frontend.

Run with: python -m pytest test_testing_prompt.py -v
"""

from pathlib import Path

import pytest

from prompts import TEMPLATES_DIR, get_testing_prompt, project_has_web_ui

WEB_SPEC = """<project_specification>
  <technology_stack>
    <frontend>
      <framework>React with Vite</framework>
    </frontend>
    <backend><runtime>Node.js</runtime></backend>
  </technology_stack>
</project_specification>
"""

CLI_SPEC = """<project_specification>
  <technology_stack>
    <backend><runtime>Python 3.11 command-line tool</runtime></backend>
  </technology_stack>
</project_specification>
"""

# Old browser-only testing prompt, as scaffolded into existing projects
LEGACY_PROMPT = """## YOUR ROLE - TESTING AGENT

Test features {{TESTING_FEATURE_IDS}}

### STEP 2: VERIFY THE FEATURE

**CRITICAL:** You MUST verify the feature through the actual UI using browser automation.

### Browser Automation (Playwright CLI)
- `playwright-cli open <url>` - Open browser

### STEP 3: HANDLE RESULTS

Mark it.

---

## AVAILABLE TOOLS

### Browser Automation (Playwright CLI)
- `playwright-cli open <url>` - Open browser

---

Begin.
"""


def _write_spec(project_dir: Path, spec: str) -> None:
    prompts_dir = project_dir / ".autoforge" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "app_spec.txt").write_text(spec, encoding="utf-8")


@pytest.mark.parametrize(
    "spec, expected",
    [
        (WEB_SPEC, True),
        (CLI_SPEC, False),
        ("<technology_stack><frontend>None</frontend></technology_stack>", False),
        ("<technology_stack><frontend>  </frontend></technology_stack>", False),
        ("<technology_stack><frontend>CLI only (no GUI)</frontend></technology_stack>", False),
        ("<technology_stack><frontend>Terminal UI with Ink</frontend></technology_stack>", False),
        ("<technology_stack><frontend>Next.js</frontend></technology_stack>", True),
        # Commented-out frontend examples don't count
        ("<technology_stack><!-- <frontend>React</frontend> --></technology_stack>", False),
        # No technology stack: can't tell
        ("<project_specification><overview>x</overview></project_specification>", None),
    ],
)
def test_project_has_web_ui(tmp_path: Path, spec: str, expected: bool | None) -> None:
    _write_spec(tmp_path, spec)
    assert project_has_web_ui(tmp_path) is expected


def test_project_has_web_ui_without_spec(tmp_path: Path) -> None:
    assert project_has_web_ui(tmp_path) is None


def test_template_offers_both_strategies() -> None:
    prompt = get_testing_prompt(None, testing_feature_ids=[1, 2])
    assert "Strategy A: Browser verification" in prompt
    assert "Strategy B: Command-line verification" in prompt
    assert "1, 2" in prompt


def test_web_project_keeps_browser_instructions(tmp_path: Path) -> None:
    _write_spec(tmp_path, WEB_SPEC)
    prompt = get_testing_prompt(tmp_path, testing_feature_ids=[3])
    assert "playwright-cli" in prompt
    assert "PROJECT TYPE: NO WEB UI" not in prompt


def test_unknown_project_type_keeps_template(tmp_path: Path) -> None:
    prompt = get_testing_prompt(tmp_path, testing_feature_ids=[3])
    assert prompt == get_testing_prompt(None, testing_feature_ids=[3])


def test_cli_project_uses_command_line_verification(tmp_path: Path) -> None:
    _write_spec(tmp_path, CLI_SPEC)
    prompt = get_testing_prompt(tmp_path, testing_feature_ids=[3])

    assert prompt.startswith("## PROJECT TYPE: NO WEB UI")
    assert "Strategy B: Command-line verification" in prompt
    assert "Strategy A" not in prompt
    assert "playwright-cli" not in prompt
    # Rest of the workflow is preserved
    assert "### STEP 3: HANDLE RESULTS" in prompt
    assert "### Command Line (Bash)" in prompt
    assert "{{TESTING_FEATURE_IDS}}" not in prompt


def test_cli_project_with_legacy_prompt(tmp_path: Path) -> None:
    _write_spec(tmp_path, CLI_SPEC)
    (tmp_path / ".autoforge" / "prompts" / "testing_prompt.md").write_text(LEGACY_PROMPT, encoding="utf-8")

    prompt = get_testing_prompt(tmp_path, testing_feature_id=7)

    assert prompt.startswith("## PROJECT TYPE: NO WEB UI")
    assert "Strategy B: Command-line verification" in prompt
    assert "playwright-cli" not in prompt
    assert "### STEP 3: HANDLE RESULTS" in prompt
    assert "## AVAILABLE TOOLS" in prompt
    assert "Test features 7" in prompt


def test_template_cli_strategy_covers_issue_steps() -> None:
    template = (TEMPLATES_DIR / "testing_prompt.template.md").read_text(encoding="utf-8")
    for heading in (
        "B0. Plan the success criteria",
        "B1. Make results observable",
        "B2. Prepare the simulated user input",
        "B3. Run the program from bash",
        "B4. Retrieve and compare results",
    ):
        assert heading in template
