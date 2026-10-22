"""
Quality Gates
=============

Auto-detects a project's linters and type checkers, runs them, and reports
structured results. Used by the feature MCP server to verify code before a
feature is marked as passing.

Quality gates are disabled by default. They are configured ONLY through
environment variables of the AutoForge process (e.g. ``~/.autoforge/.env``),
never through files inside the project, because the coding agent can write
anything in the project directory and must not be able to turn the gates on
(or weaken them)::

    AUTOFORGE_QUALITY_GATES=strict        # off (default) | strict (or 1/true/on) | warn
    AUTOFORGE_QUALITY_GATES_TIMEOUT=120   # per-check timeout in seconds (max 600)
    AUTOFORGE_QUALITY_GATES_CHECKS=lint,type_check

In ``strict`` mode ``feature_mark_passing`` refuses to mark a feature as
passing while any check fails. In ``warn`` mode the checks still run and are
recorded, but failures are reported as warnings only.

SECURITY / TRUST: the checks run inside the feature MCP server process, which
is NOT covered by the agent's Bash sandbox or the command allowlist in
``security.py``. They execute project-local tooling and configuration that the
agent can modify (``node_modules/.bin/*``, ``.venv``/``venv``,
``eslint.config.js`` and similar). Enabling quality gates is therefore a trust
decision: only enable them for projects whose contents you trust to run
unsandboxed on your machine.

Detected tools (only run when the project is configured for them):

- Lint: ESLint, Biome, ruff, flake8
- Type check: TypeScript (``tsc --noEmit``, or ``tsc --build --noEmit`` for
  project references), mypy

Node tools are only run from the project's ``node_modules/.bin`` and Python
tools only when installed, so a check never triggers a package download.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_SECONDS = 120
MAX_TIMEOUT_SECONDS = 600
# Keep stored output small - it lands in the features database and in MCP responses
MAX_OUTPUT_CHARS = 4000

ESLINT_CONFIGS = (
    "eslint.config.js", "eslint.config.mjs", "eslint.config.cjs",
    "eslint.config.ts", "eslint.config.mts", "eslint.config.cts",
    ".eslintrc", ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json",
    ".eslintrc.yml", ".eslintrc.yaml",
)
BIOME_CONFIGS = ("biome.json", "biome.jsonc")
FLAKE8_CONFIGS = (".flake8",)

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


@dataclass
class QualityGateConfig:
    """Effective quality-gate settings for a project."""

    enabled: bool = False
    strict_mode: bool = True
    lint: bool = True
    type_check: bool = True
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


@dataclass
class QualityCheck:
    """A single check to run: a name, a category and the command line."""

    name: str
    category: str  # "lint" or "type_check"
    command: list[str]


@dataclass
class CheckResult:
    """Outcome of running one quality check."""

    name: str
    category: str
    command: str
    passed: bool
    exit_code: int | None
    duration_seconds: float
    output: str
    timed_out: bool = False


@dataclass
class QualityReport:
    """Aggregate result of all quality checks for a project."""

    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    strict_mode: bool = True
    timestamp: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


ENV_ENABLED = "AUTOFORGE_QUALITY_GATES"
ENV_TIMEOUT = "AUTOFORGE_QUALITY_GATES_TIMEOUT"
ENV_CHECKS = "AUTOFORGE_QUALITY_GATES_CHECKS"

# Environment variables forwarded to the feature MCP server (see client.py)
QUALITY_GATE_ENV_VARS = (ENV_ENABLED, ENV_TIMEOUT, ENV_CHECKS)

_STRICT_VALUES = {"1", "true", "yes", "on", "strict"}
_WARN_VALUES = {"warn", "warning"}


def load_config(env: dict[str, str] | None = None) -> QualityGateConfig:
    """Load quality gate settings from environment variables.

    Deliberately ignores any file in the project directory: the agent can
    write there, and enabling the gates runs project tooling unsandboxed.
    Unknown or malformed values fall back to safe defaults (disabled).
    """
    if env is None:
        env = dict(os.environ)
    config = QualityGateConfig()

    mode = env.get(ENV_ENABLED, "").strip().lower()
    if mode in _STRICT_VALUES:
        config.enabled = True
        config.strict_mode = True
    elif mode in _WARN_VALUES:
        config.enabled = True
        config.strict_mode = False
    elif mode not in ("", "0", "false", "no", "off"):
        print(f"[quality_gates] Ignoring unknown {ENV_ENABLED}={mode!r}; gates disabled", file=sys.stderr)

    timeout = env.get(ENV_TIMEOUT, "").strip()
    if timeout:
        try:
            value = int(timeout)
        except ValueError:
            value = 0
        if value > 0:
            config.timeout_seconds = min(value, MAX_TIMEOUT_SECONDS)

    checks = env.get(ENV_CHECKS)
    if checks is not None and checks.strip():
        names = {c.strip().lower().replace("-", "_") for c in checks.split(",")}
        config.lint = "lint" in names
        config.type_check = "type_check" in names

    return config


def _node_bin(project_dir: Path, name: str) -> str | None:
    """Return the project-local Node binary, or None if not installed."""
    bin_dir = project_dir / "node_modules" / ".bin"
    candidates = [f"{name}.cmd", name] if sys.platform == "win32" else [name]
    for candidate in candidates:
        path = bin_dir / candidate
        if path.is_file():
            return str(path)
    return None


def _python_tool(project_dir: Path, name: str) -> list[str] | None:
    """Return a command prefix for a Python tool, or None if unavailable.

    Prefers the project's own virtualenv so the tool sees the project's
    dependencies, then falls back to PATH.
    """
    scripts = "Scripts" if sys.platform == "win32" else "bin"
    exe = f"{name}.exe" if sys.platform == "win32" else name
    for venv in (".venv", "venv"):
        path = project_dir / venv / scripts / exe
        if path.is_file():
            return [str(path)]
    found = shutil.which(name)
    if found:
        return [found]
    return None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _package_json(project_dir: Path) -> dict[str, Any]:
    text = _read_text(project_dir / "package.json")
    if not text:
        return {}
    try:
        data = json.loads(text)
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _has_python_sources(project_dir: Path) -> bool:
    markers = ("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt")
    return any((project_dir / m).is_file() for m in markers)


def detect_checks(project_dir: Path, config: QualityGateConfig | None = None) -> list[QualityCheck]:
    """Detect which linters and type checkers apply to a project."""
    # Absolute paths: the commands run with cwd=project_dir
    project_dir = project_dir.resolve()
    if config is None:
        config = load_config()

    checks: list[QualityCheck] = []
    pkg = _package_json(project_dir)
    pyproject = _read_text(project_dir / "pyproject.toml")
    setup_cfg = _read_text(project_dir / "setup.cfg")
    tox_ini = _read_text(project_dir / "tox.ini")
    is_python = _has_python_sources(project_dir)

    if config.lint:
        has_eslint_config = (
            any((project_dir / c).is_file() for c in ESLINT_CONFIGS) or "eslintConfig" in pkg
        )
        eslint = _node_bin(project_dir, "eslint")
        if has_eslint_config and eslint:
            checks.append(QualityCheck("eslint", "lint", [eslint, "."]))

        biome = _node_bin(project_dir, "biome")
        if any((project_dir / c).is_file() for c in BIOME_CONFIGS) and biome:
            checks.append(QualityCheck("biome", "lint", [biome, "lint", "."]))

        has_ruff_config = (
            (project_dir / "ruff.toml").is_file()
            or (project_dir / ".ruff.toml").is_file()
            or "[tool.ruff" in pyproject
        )
        has_flake8_config = (
            any((project_dir / c).is_file() for c in FLAKE8_CONFIGS)
            or "[flake8]" in setup_cfg
            or "[flake8]" in tox_ini
        )
        ruff = _python_tool(project_dir, "ruff")
        flake8 = _python_tool(project_dir, "flake8")
        if has_ruff_config and ruff:
            checks.append(QualityCheck("ruff", "lint", [*ruff, "check", "."]))
        elif has_flake8_config and flake8:
            checks.append(QualityCheck("flake8", "lint", [*flake8, "."]))

    if config.type_check:
        tsc = _node_bin(project_dir, "tsc")
        tsconfig = project_dir / "tsconfig.json"
        if tsconfig.is_file() and tsc:
            # Solution-style configs (Vite's default) list no files of their own and
            # only reference sub-projects, which plain `tsc` would skip
            if '"references"' in _read_text(tsconfig):
                checks.append(QualityCheck("tsc", "type_check", [tsc, "--build", "--noEmit"]))
            else:
                checks.append(QualityCheck("tsc", "type_check", [tsc, "--noEmit"]))

        has_mypy_config = (
            (project_dir / "mypy.ini").is_file()
            or (project_dir / ".mypy.ini").is_file()
            or "[tool.mypy" in pyproject
            or "[mypy" in setup_cfg
        )
        mypy = _python_tool(project_dir, "mypy")
        if is_python and has_mypy_config and mypy:
            checks.append(QualityCheck("mypy", "type_check", [*mypy, "."]))

    return checks


def _clean_output(output: str) -> str:
    """Strip color codes and keep stored output to a bounded size."""
    output = ANSI_ESCAPE_RE.sub("", output).strip()
    if len(output) <= MAX_OUTPUT_CHARS:
        return output
    # Keep the tail - linters usually print the summary last
    return "...(truncated)...\n" + output[-MAX_OUTPUT_CHARS:]


def run_check(check: QualityCheck, project_dir: Path, timeout: int) -> CheckResult:
    """Run a single check in the project directory."""
    start = time.monotonic()
    env = {**os.environ, "CI": "1", "NO_COLOR": "1"}
    # Some tools treat any FORCE_COLOR value (even "0") as "force color on"
    env.pop("FORCE_COLOR", None)
    try:
        proc = subprocess.run(
            check.command,
            cwd=project_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            stdin=subprocess.DEVNULL,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return CheckResult(
            name=check.name,
            category=check.category,
            command=" ".join([Path(check.command[0]).name, *check.command[1:]]),
            passed=proc.returncode == 0,
            exit_code=proc.returncode,
            duration_seconds=round(time.monotonic() - start, 2),
            output=_clean_output(output),
        )
    except subprocess.TimeoutExpired as e:
        partial = e.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", errors="replace")
        return CheckResult(
            name=check.name,
            category=check.category,
            command=" ".join([Path(check.command[0]).name, *check.command[1:]]),
            passed=False,
            exit_code=None,
            duration_seconds=round(time.monotonic() - start, 2),
            output=_clean_output(f"{partial}\nTimed out after {timeout}s"),
            timed_out=True,
        )
    except OSError as e:
        return CheckResult(
            name=check.name,
            category=check.category,
            command=" ".join([Path(check.command[0]).name, *check.command[1:]]),
            passed=False,
            exit_code=None,
            duration_seconds=round(time.monotonic() - start, 2),
            output=f"Failed to run {check.name}: {e}",
        )


def run_quality_checks(project_dir: Path, config: QualityGateConfig | None = None) -> QualityReport:
    """Detect and run all applicable quality checks for a project."""
    project_dir = project_dir.resolve()
    if config is None:
        config = load_config()

    # Defense in depth: never execute project tooling unless the trusted switch is on
    if not config.enabled:
        return QualityReport(
            passed=True,
            strict_mode=config.strict_mode,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message="Quality gates are disabled; nothing was run",
        )

    checks = detect_checks(project_dir, config)
    results = [run_check(c, project_dir, config.timeout_seconds) for c in checks]
    passed = all(r.passed for r in results)

    if not results:
        message = "No linters or type checkers detected; nothing to verify"
    elif passed:
        message = f"All {len(results)} quality check(s) passed: " + ", ".join(r.name for r in results)
    else:
        failed = [r.name for r in results if not r.passed]
        message = f"{len(failed)} of {len(results)} quality check(s) failed: " + ", ".join(failed)

    return QualityReport(
        passed=passed,
        checks=results,
        strict_mode=config.strict_mode,
        timestamp=datetime.now(timezone.utc).isoformat(),
        message=message,
    )
