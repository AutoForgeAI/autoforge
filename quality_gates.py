"""
Quality Gates
=============

Auto-detects a project's linters and type checkers, runs them, and reports
the results. Used by the feature MCP server to verify code before a feature
is marked as passing.

Quality gates are opt-in per project via ``.autoforge/config.json``::

    {
      "quality_gates": {
        "enabled": true,
        "strict_mode": true,
        "checks": {"lint": true, "type_check": true},
        "timeout_seconds": 300
      }
    }

- ``enabled``: run checks automatically inside ``feature_mark_passing``.
- ``strict_mode``: refuse to mark a feature passing when a check fails.
  When false, the feature is still marked passing and the failure is
  returned as a warning (and stored as evidence).
- ``checks``: toggle linting / type checking individually.
- ``timeout_seconds``: per-check timeout.

Only well-known tools are run, and only from the project's own install
(``node_modules/.bin``, ``.venv``/``venv``) or the PATH. Commands are never
read from the config file. Note that tools such as ESLint load configuration
files written by the agent, and the MCP server is not inside the bash
sandbox, so only enable quality gates for projects you trust the agent with.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Keep stored evidence compact: only the tail of each tool's output is kept
MAX_OUTPUT_CHARS = 4000
DEFAULT_TIMEOUT_SECONDS = 300

CONFIG_FILENAME = "config.json"


@dataclass
class QualityGateConfig:
    """Per-project quality gate settings."""

    enabled: bool = False
    strict_mode: bool = True
    lint: bool = True
    type_check: bool = True
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


@dataclass
class QualityCheck:
    """A detected check: a tool and the command that runs it."""

    name: str
    kind: str  # "lint" or "type_check"
    command: list[str]


@dataclass
class CheckResult:
    name: str
    kind: str
    command: str
    passed: bool
    returncode: int | None
    duration_seconds: float
    output: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "command": self.command,
            "passed": self.passed,
            "returncode": self.returncode,
            "duration_seconds": self.duration_seconds,
            "output": self.output,
        }


@dataclass
class QualityReport:
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    timestamp: str = ""

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def summary(self) -> str:
        if not self.checks:
            return "No linters or type checkers detected"
        parts = [f"{c.name}: {'passed' if c.passed else 'FAILED'}" for c in self.checks]
        return ", ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "summary": self.summary(),
            "timestamp": self.timestamp,
            "checks": [c.to_dict() for c in self.checks],
        }


def get_config_path(project_dir: Path) -> Path:
    """Return the path to the project's ``.autoforge/config.json``."""
    from autoforge_paths import get_autoforge_dir
    return get_autoforge_dir(project_dir) / CONFIG_FILENAME


def load_config(project_dir: Path) -> QualityGateConfig:
    """Load quality gate settings. Missing or malformed config means disabled."""
    config_path = get_config_path(project_dir)
    if not config_path.is_file():
        return QualityGateConfig()

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return QualityGateConfig()

    section = data.get("quality_gates") if isinstance(data, dict) else None
    if not isinstance(section, dict):
        return QualityGateConfig()

    checks = section.get("checks")
    if not isinstance(checks, dict):
        checks = {}

    timeout = section.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        timeout = DEFAULT_TIMEOUT_SECONDS

    return QualityGateConfig(
        enabled=section.get("enabled") is True,
        strict_mode=section.get("strict_mode", True) is not False,
        lint=checks.get("lint", True) is not False,
        type_check=checks.get("type_check", True) is not False,
        timeout_seconds=timeout,
    )


# ---------------------------------------------------------------------------
# Tool detection
# ---------------------------------------------------------------------------

def _find_node_bin(project_dir: Path, name: str) -> str | None:
    """Locate a locally installed Node tool (never npx, which may download)."""
    bin_dir = project_dir / "node_modules" / ".bin"
    candidates = [f"{name}.cmd", f"{name}.exe", name] if sys.platform == "win32" else [name]
    for candidate in candidates:
        path = bin_dir / candidate
        if path.is_file():
            return str(path)
    return None


def _find_python_bin(project_dir: Path, name: str) -> str | None:
    """Locate a Python tool in the project's virtualenv, falling back to PATH."""
    if sys.platform == "win32":
        rel_paths = [Path("Scripts") / f"{name}.exe"]
    else:
        rel_paths = [Path("bin") / name]
    for venv_name in (".venv", "venv"):
        for rel in rel_paths:
            path = project_dir / venv_name / rel
            if path.is_file():
                return str(path)
    return shutil.which(name)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _any_exists(project_dir: Path, names: list[str]) -> bool:
    return any((project_dir / n).is_file() for n in names)


def _has_section(project_dir: Path, filename: str, marker: str) -> bool:
    return marker in _read_text(project_dir / filename)


def detect_checks(project_dir: Path) -> list[QualityCheck]:
    """Detect the linters and type checkers configured for a project.

    A tool is only selected when the project both configures it and has it
    installed, so we never fail a gate because of a tool the project
    doesn't use.
    """
    checks: list[QualityCheck] = []

    # --- JavaScript / TypeScript ---
    if (project_dir / "package.json").is_file():
        biome = _find_node_bin(project_dir, "biome")
        eslint = _find_node_bin(project_dir, "eslint")
        has_biome_config = _any_exists(project_dir, ["biome.json", "biome.jsonc"])
        has_eslint_config = _any_exists(project_dir, [
            "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
            "eslint.config.ts", "eslint.config.mts", "eslint.config.cts",
            ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
            ".eslintrc.yml", ".eslintrc.yaml",
        ]) or '"eslintConfig"' in _read_text(project_dir / "package.json")

        if has_biome_config and biome:
            checks.append(QualityCheck("biome", "lint", [biome, "lint", "."]))
        elif has_eslint_config and eslint:
            checks.append(QualityCheck("eslint", "lint", [eslint, "."]))

        tsc = _find_node_bin(project_dir, "tsc")
        if (project_dir / "tsconfig.json").is_file() and tsc:
            if '"references"' in _read_text(project_dir / "tsconfig.json"):
                # Solution-style config (e.g. Vite templates): a plain -p run
                # checks no files, so build the referenced projects instead
                command = [tsc, "-b", "--noEmit"]
            else:
                command = [tsc, "--noEmit", "-p", "tsconfig.json"]
            checks.append(QualityCheck("tsc", "type_check", command))

    # --- Python ---
    has_ruff_config = _any_exists(project_dir, ["ruff.toml", ".ruff.toml"]) or _has_section(
        project_dir, "pyproject.toml", "[tool.ruff"
    )
    has_flake8_config = (
        (project_dir / ".flake8").is_file()
        or _has_section(project_dir, "setup.cfg", "[flake8]")
        or _has_section(project_dir, "tox.ini", "[flake8]")
    )
    if has_ruff_config:
        ruff = _find_python_bin(project_dir, "ruff")
        if ruff:
            checks.append(QualityCheck("ruff", "lint", [ruff, "check", "."]))
    elif has_flake8_config:
        flake8 = _find_python_bin(project_dir, "flake8")
        if flake8:
            checks.append(QualityCheck("flake8", "lint", [flake8, "."]))

    has_mypy_config = (
        _any_exists(project_dir, ["mypy.ini", ".mypy.ini"])
        or _has_section(project_dir, "pyproject.toml", "[tool.mypy")
        or _has_section(project_dir, "setup.cfg", "[mypy")
    )
    if has_mypy_config:
        mypy = _find_python_bin(project_dir, "mypy")
        if mypy:
            checks.append(QualityCheck("mypy", "type_check", [mypy, "."]))

    return checks


# ---------------------------------------------------------------------------
# Running checks
# ---------------------------------------------------------------------------

def _truncate(output: str) -> str:
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    return "...(truncated)...\n" + output[-MAX_OUTPUT_CHARS:]


def _run_check(check: QualityCheck, project_dir: Path, timeout: int) -> CheckResult:
    start = time.monotonic()
    command_str = " ".join([Path(check.command[0]).name, *check.command[1:]])
    try:
        proc = subprocess.run(
            check.command,
            cwd=project_dir,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env={**os.environ, "CI": "1", "NO_COLOR": "1"},
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return CheckResult(
            name=check.name,
            kind=check.kind,
            command=command_str,
            passed=proc.returncode == 0,
            returncode=proc.returncode,
            duration_seconds=round(time.monotonic() - start, 2),
            output=_truncate(output.strip()),
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=check.name,
            kind=check.kind,
            command=command_str,
            passed=False,
            returncode=None,
            duration_seconds=round(time.monotonic() - start, 2),
            output=f"Timed out after {timeout} seconds",
        )
    except OSError as e:
        return CheckResult(
            name=check.name,
            kind=check.kind,
            command=command_str,
            passed=False,
            returncode=None,
            duration_seconds=round(time.monotonic() - start, 2),
            output=f"Failed to run: {e}",
        )


def run_quality_checks(project_dir: Path, config: QualityGateConfig | None = None) -> QualityReport:
    """Detect and run the project's quality checks.

    Checks disabled in the config are skipped. A project with no detected
    tools passes trivially (there is nothing to verify).
    """
    if config is None:
        config = load_config(project_dir)

    checks = [
        c for c in detect_checks(project_dir)
        if (c.kind == "lint" and config.lint) or (c.kind == "type_check" and config.type_check)
    ]
    results = [_run_check(c, project_dir, config.timeout_seconds) for c in checks]

    return QualityReport(
        passed=all(r.passed for r in results),
        checks=results,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def format_failure_reason(report: QualityReport) -> str:
    """Short, human-readable reason for a failed report (stored in failure_reason)."""
    failed = report.failed_checks
    if not failed:
        return ""
    names = ", ".join(c.name for c in failed)
    return f"Quality gate failed: {names}"
