"""
Scripted Regression Tests
=========================

Runs per-feature automated regression test scripts so that testing agents
don't need an LLM session to re-verify features that already have a script.

Testing agents author these scripts the first time they verify a feature and
register them in a manifest committed with the generated app:

    tests/regression/manifest.json
    {
      "12": {"command": "npx playwright test tests/regression/feature_12.spec.ts"},
      "15": {"command": "node tests/regression/feature_15.mjs", "timeout": 120}
    }

Before starting an LLM session, the testing agent runs the scripts for its
assigned features. Features whose scripts pass are done without spending any
tokens; features without a script (or whose script failed) are handed to the
LLM, which verifies them, fixes regressions and writes/repairs the script.

Commands are validated against the same bash allowlist the agent itself is
subject to (security.validate_bash_command) and run from the project root.
"""

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from security import validate_bash_command
from server.utils.process_utils import kill_process_tree

# Manifest location, relative to the project directory
REGRESSION_MANIFEST = Path("tests") / "regression" / "manifest.json"

DEFAULT_TIMEOUT_SECONDS = 300
MAX_TIMEOUT_SECONDS = 900

# How much of a failing script's output to hand to the LLM
OUTPUT_TAIL_CHARS = 4000


@dataclass
class ScriptResult:
    """Outcome of running one feature's regression script."""

    feature_id: int
    command: str
    passed: bool
    duration: float
    output: str


@dataclass
class ScriptedRegressionReport:
    """Aggregated outcome of a scripted regression run for a batch of features."""

    passed: list[int] = field(default_factory=list)
    failed: list[ScriptResult] = field(default_factory=list)
    unscripted: list[int] = field(default_factory=list)

    @property
    def needs_agent(self) -> list[int]:
        """Feature IDs that still need an LLM testing session (failed first)."""
        return [r.feature_id for r in self.failed] + self.unscripted


def load_regression_manifest(project_dir: Path) -> dict[int, dict]:
    """Load the regression manifest, returning {feature_id: entry}.

    Invalid or missing manifests yield an empty mapping (every feature is then
    treated as unscripted and falls back to agent-driven testing).
    """
    path = project_dir / REGRESSION_MANIFEST
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"Warning: could not read {REGRESSION_MANIFEST}: {e}")
        return {}
    if not isinstance(raw, dict):
        print(f"Warning: {REGRESSION_MANIFEST} must be a JSON object keyed by feature ID")
        return {}

    manifest: dict[int, dict] = {}
    for key, entry in raw.items():
        try:
            feature_id = int(key)
        except (TypeError, ValueError):
            continue
        # Allow the shorthand {"12": "npm run test:feature-12"}
        if isinstance(entry, str):
            entry = {"command": entry}
        if not isinstance(entry, dict):
            continue
        command = entry.get("command")
        if isinstance(command, str) and command.strip():
            manifest[feature_id] = entry
    return manifest


def _entry_timeout(entry: dict) -> float:
    timeout = entry.get("timeout", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        return DEFAULT_TIMEOUT_SECONDS
    return min(float(timeout), MAX_TIMEOUT_SECONDS)


def _tail(text: str, limit: int = OUTPUT_TAIL_CHARS) -> str:
    return text if len(text) <= limit else "...\n" + text[-limit:]


def run_feature_script(project_dir: Path, feature_id: int, entry: dict) -> ScriptResult:
    """Run a single feature's regression command and report the result."""
    command = entry["command"].strip()

    allowed, reason = validate_bash_command(command, project_dir)
    if not allowed:
        return ScriptResult(feature_id, command, False, 0.0,
                            f"Regression command rejected by security policy: {reason}")

    popen_kwargs: dict = {
        "cwd": str(project_dir),
        "shell": True,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    start = time.monotonic()
    try:
        proc = subprocess.Popen(command, **popen_kwargs)
    except OSError as e:
        return ScriptResult(feature_id, command, False, 0.0, f"Failed to start regression command: {e}")

    timeout = _entry_timeout(entry)
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill the whole tree so browsers/dev servers spawned by the test don't linger
        kill_process_tree(proc, timeout=2.0)
        output, _ = proc.communicate()
        return ScriptResult(feature_id, command, False, time.monotonic() - start,
                            _tail((output or "") + f"\n[timed out after {timeout:.0f}s]"))

    return ScriptResult(feature_id, command, proc.returncode == 0,
                        time.monotonic() - start, _tail(output or ""))


def run_scripted_regression(project_dir: Path, feature_ids: list[int]) -> ScriptedRegressionReport:
    """Run regression scripts for the given features.

    Features with no manifest entry are reported as unscripted.
    """
    report = ScriptedRegressionReport()
    manifest = load_regression_manifest(project_dir)

    for feature_id in feature_ids:
        entry = manifest.get(feature_id)
        if entry is None:
            report.unscripted.append(feature_id)
            continue

        print(f"[Feature #{feature_id}] Running scripted regression test: {entry['command']}", flush=True)
        result = run_feature_script(project_dir, feature_id, entry)
        status = "PASSED" if result.passed else "FAILED"
        print(f"[Feature #{feature_id}] Scripted regression test {status} ({result.duration:.1f}s)", flush=True)
        if result.passed:
            report.passed.append(feature_id)
        else:
            report.failed.append(result)

    return report


def format_failures_for_prompt(failed: list[ScriptResult]) -> str:
    """Describe failing scripts so the testing agent can start from the evidence."""
    if not failed:
        return ""
    lines = [
        "## SCRIPTED REGRESSION FAILURES",
        "",
        "The automated regression scripts below FAILED before this session started. "
        "For each one, determine whether the feature has regressed (fix the app) or "
        "the script itself is broken/flaky (fix the script). Re-run the command and make "
        "sure it passes before ending your session.",
        "",
    ]
    for r in failed:
        lines += [
            f"### Feature #{r.feature_id}",
            f"Command: `{r.command}`",
            "Output (tail):",
            "```",
            r.output.strip() or "(no output)",
            "```",
            "",
        ]
    return "\n".join(lines)
