"""
Quality Gates Tests
===================

Tests for quality_gates.py and the quality gate integration in the feature
MCP server (feature_mark_passing, feature_verify_quality, feature_report_failure).

Run with: python -m pytest test_quality_gates.py
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

import quality_gates
from api.database import Feature, create_database, dispose_engine
from mcp_server import feature_mcp
from quality_gates import QualityCheck, QualityGateConfig


def _write_project_config(project_dir: Path, section: dict) -> None:
    """Write the (ignored) legacy per-project config an agent could create."""
    autoforge_dir = project_dir / ".autoforge"
    autoforge_dir.mkdir(parents=True, exist_ok=True)
    (autoforge_dir / "config.json").write_text(json.dumps({"quality_gates": section}))


def _enable(monkeypatch, mode: str = "strict") -> None:
    monkeypatch.setenv(quality_gates.ENV_ENABLED, mode)


def _py_check(name: str, category: str, code: str) -> QualityCheck:
    return QualityCheck(name, category, [sys.executable, "-c", code])


@pytest.fixture(autouse=True)
def _clean_quality_env(monkeypatch):
    """Never let the developer's own environment leak into the tests."""
    for var in quality_gates.QUALITY_GATE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


# =============================================================================
# Config loading
# =============================================================================


def test_config_defaults_to_disabled():
    config = quality_gates.load_config({})
    assert config.enabled is False
    assert config.strict_mode is True
    assert config.lint is True
    assert config.type_check is True


@pytest.mark.parametrize("value", ["strict", "1", "true", "ON", " Strict "])
def test_config_strict_values(value):
    config = quality_gates.load_config({quality_gates.ENV_ENABLED: value})
    assert config.enabled is True
    assert config.strict_mode is True


def test_config_warn_mode():
    config = quality_gates.load_config({quality_gates.ENV_ENABLED: "warn"})
    assert config.enabled is True
    assert config.strict_mode is False


@pytest.mark.parametrize("value", ["", "0", "off", "false", "maybe"])
def test_config_disabled_values(value):
    assert quality_gates.load_config({quality_gates.ENV_ENABLED: value}).enabled is False


def test_config_reads_timeout_and_checks():
    config = quality_gates.load_config({
        quality_gates.ENV_ENABLED: "strict",
        quality_gates.ENV_TIMEOUT: "30",
        quality_gates.ENV_CHECKS: "type-check",
    })
    assert config.timeout_seconds == 30
    assert config.lint is False
    assert config.type_check is True


def test_config_ignores_bad_timeout():
    config = quality_gates.load_config({quality_gates.ENV_TIMEOUT: "-5"})
    assert config.timeout_seconds == quality_gates.DEFAULT_TIMEOUT_SECONDS
    config = quality_gates.load_config({quality_gates.ENV_TIMEOUT: "soon"})
    assert config.timeout_seconds == quality_gates.DEFAULT_TIMEOUT_SECONDS


def test_config_caps_timeout():
    config = quality_gates.load_config({quality_gates.ENV_TIMEOUT: "99999"})
    assert config.timeout_seconds == quality_gates.MAX_TIMEOUT_SECONDS


def test_config_reads_process_environment(monkeypatch):
    _enable(monkeypatch, "warn")
    config = quality_gates.load_config()
    assert config.enabled is True
    assert config.strict_mode is False


def test_project_config_file_cannot_enable_gates(tmp_path, monkeypatch):
    """The agent can write .autoforge/config.json, so it must have no effect."""
    _write_project_config(tmp_path, {"enabled": True, "strict_mode": True})
    monkeypatch.chdir(tmp_path)
    assert quality_gates.load_config().enabled is False


def test_disabled_config_runs_nothing(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("no checks may be detected or run while disabled")

    monkeypatch.setattr(quality_gates, "detect_checks", boom)
    report = quality_gates.run_quality_checks(tmp_path, QualityGateConfig(enabled=False))
    assert report.checks == []
    assert "disabled" in report.message


# =============================================================================
# Detection
# =============================================================================


def _fake_node_bin(project_dir: Path, name: str) -> None:
    bin_dir = project_dir / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{name}.cmd" if sys.platform == "win32" else name
    (bin_dir / filename).write_text("")


def test_detects_nothing_in_empty_project(tmp_path):
    assert quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True)) == []


def test_detects_eslint_and_tsc(tmp_path):
    (tmp_path / "eslint.config.js").write_text("export default []")
    (tmp_path / "tsconfig.json").write_text("{}")
    _fake_node_bin(tmp_path, "eslint")
    _fake_node_bin(tmp_path, "tsc")

    checks = quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True))
    assert [c.name for c in checks] == ["eslint", "tsc"]
    assert checks[1].command[1:] == ["--noEmit"]


def test_tsc_uses_build_mode_for_project_references(tmp_path):
    (tmp_path / "tsconfig.json").write_text('{"files": [], "references": [{"path": "./tsconfig.app.json"}]}')
    _fake_node_bin(tmp_path, "tsc")
    checks = quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True))
    assert checks[0].command[1:] == ["--build", "--noEmit"]


def test_node_tools_require_local_install(tmp_path):
    """Config alone is not enough: we never fall back to npx (which may download packages)."""
    (tmp_path / "eslint.config.js").write_text("export default []")
    (tmp_path / "tsconfig.json").write_text("{}")
    assert quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True)) == []


def test_detects_biome(tmp_path):
    (tmp_path / "biome.json").write_text("{}")
    _fake_node_bin(tmp_path, "biome")
    checks = quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True))
    assert [c.name for c in checks] == ["biome"]
    assert checks[0].command[1:] == ["lint", "."]


def test_detects_python_tools(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n\n[tool.mypy]\n")
    monkeypatch.setattr(quality_gates.shutil, "which", lambda name: f"/usr/bin/{name}")

    checks = quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True))
    assert [(c.name, c.category) for c in checks] == [("ruff", "lint"), ("mypy", "type_check")]


def test_prefers_ruff_over_flake8(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    (tmp_path / ".flake8").write_text("[flake8]\n")
    monkeypatch.setattr(quality_gates.shutil, "which", lambda name: f"/usr/bin/{name}")

    names = [c.name for c in quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True))]
    assert names == ["ruff"]


def test_detects_flake8(tmp_path, monkeypatch):
    (tmp_path / "setup.cfg").write_text("[flake8]\nmax-line-length = 100\n")
    monkeypatch.setattr(quality_gates.shutil, "which", lambda name: f"/usr/bin/{name}")

    names = [c.name for c in quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True))]
    assert names == ["flake8"]


def test_prefers_project_venv(tmp_path, monkeypatch):
    (tmp_path / "ruff.toml").write_text("")
    scripts = tmp_path / ".venv" / ("Scripts" if sys.platform == "win32" else "bin")
    scripts.mkdir(parents=True)
    exe = scripts / ("ruff.exe" if sys.platform == "win32" else "ruff")
    exe.write_text("")
    monkeypatch.setattr(quality_gates.shutil, "which", lambda name: f"/usr/bin/{name}")

    checks = quality_gates.detect_checks(tmp_path, QualityGateConfig(enabled=True))
    assert checks[0].command[0] == str(exe)


def test_respects_disabled_check_categories(tmp_path):
    (tmp_path / "eslint.config.js").write_text("export default []")
    (tmp_path / "tsconfig.json").write_text("{}")
    _fake_node_bin(tmp_path, "eslint")
    _fake_node_bin(tmp_path, "tsc")

    lint_only = QualityGateConfig(enabled=True, type_check=False)
    assert [c.name for c in quality_gates.detect_checks(tmp_path, lint_only)] == ["eslint"]

    types_only = QualityGateConfig(enabled=True, lint=False)
    assert [c.name for c in quality_gates.detect_checks(tmp_path, types_only)] == ["tsc"]


# =============================================================================
# Running checks
# =============================================================================


def test_run_check_pass_and_fail(tmp_path):
    ok = quality_gates.run_check(_py_check("ok", "lint", "print('clean')"), tmp_path, 30)
    assert ok.passed is True
    assert ok.exit_code == 0
    assert "clean" in ok.output

    bad = quality_gates.run_check(
        _py_check("bad", "lint", "import sys; print('error: x'); sys.exit(2)"), tmp_path, 30
    )
    assert bad.passed is False
    assert bad.exit_code == 2
    assert "error: x" in bad.output


def test_run_check_timeout(tmp_path):
    result = quality_gates.run_check(_py_check("slow", "lint", "import time; time.sleep(5)"), tmp_path, 1)
    assert result.passed is False
    assert result.timed_out is True
    assert "Timed out" in result.output


def test_run_check_missing_binary(tmp_path):
    check = QualityCheck("ghost", "lint", [str(tmp_path / "does-not-exist")])
    result = quality_gates.run_check(check, tmp_path, 5)
    assert result.passed is False
    assert "Failed to run ghost" in result.output


def test_run_check_truncates_output(tmp_path):
    code = f"print('x' * {quality_gates.MAX_OUTPUT_CHARS * 2})"
    result = quality_gates.run_check(_py_check("noisy", "lint", code), tmp_path, 30)
    assert len(result.output) < quality_gates.MAX_OUTPUT_CHARS + 100


def test_report_with_no_checks_passes(tmp_path):
    report = quality_gates.run_quality_checks(tmp_path, QualityGateConfig(enabled=True))
    assert report.passed is True
    assert report.checks == []
    assert "No linters" in report.message


# =============================================================================
# Database migration
# =============================================================================


def test_migration_adds_quality_columns(tmp_path):
    db_dir = tmp_path / ".autoforge"
    db_dir.mkdir()
    conn = sqlite3.connect(db_dir / "features.db")
    conn.execute("""
        CREATE TABLE features (
            id INTEGER PRIMARY KEY, priority INTEGER NOT NULL, category VARCHAR(100) NOT NULL,
            name VARCHAR(255) NOT NULL, description TEXT NOT NULL, steps JSON NOT NULL,
            passes BOOLEAN NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO features (priority, category, name, description, steps, passes) "
        "VALUES (1, 'c', 'old', 'd', '[]', 0)"
    )
    conn.commit()
    conn.close()

    try:
        _, session_maker = create_database(tmp_path)
        session = session_maker()
        try:
            feature = session.query(Feature).first()
            data = feature.to_dict()
            assert data["failure_count"] == 0
            assert data["failure_reason"] is None
            assert data["quality_result"] is None
        finally:
            session.close()
    finally:
        dispose_engine(tmp_path)


# =============================================================================
# MCP integration
# =============================================================================


@pytest.fixture
def mcp_project(tmp_path, monkeypatch):
    """A project with one in-progress feature, wired into the feature MCP module."""
    engine, session_maker = create_database(tmp_path)
    session = session_maker()
    session.add(Feature(
        id=1, priority=1, category="core", name="Login", description="d",
        steps=["s"], passes=False, in_progress=True,
    ))
    session.commit()
    session.close()

    monkeypatch.setattr(feature_mcp, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(feature_mcp, "_session_maker", session_maker)
    yield tmp_path, session_maker
    dispose_engine(tmp_path)


def _feature(session_maker) -> Feature:
    session = session_maker()
    try:
        feature: Feature = session.query(Feature).filter(Feature.id == 1).one()
        return feature
    finally:
        session.close()


def _set_checks(monkeypatch, checks: list[QualityCheck]) -> None:
    monkeypatch.setattr(quality_gates, "detect_checks", lambda project_dir, config=None: checks)


FAILING = _py_check("ruff", "lint", "import sys; print('E501 line too long'); sys.exit(1)")
PASSING = _py_check("tsc", "type_check", "pass")


def test_mark_passing_unchanged_when_disabled(mcp_project, monkeypatch):
    project_dir, session_maker = mcp_project
    _set_checks(monkeypatch, [FAILING])

    result = json.loads(feature_mcp.feature_mark_passing(1))
    assert result["success"] is True
    assert "quality_gates" not in result
    feature = _feature(session_maker)
    assert feature.passes is True
    assert feature.quality_result is None


def test_strict_mode_blocks_failing_checks(mcp_project, monkeypatch):
    project_dir, session_maker = mcp_project
    _enable(monkeypatch)
    _set_checks(monkeypatch, [PASSING, FAILING])

    result = json.loads(feature_mcp.feature_mark_passing(1))
    assert "error" in result
    assert "NOT marked passing" in result["error"]
    failed = [c for c in result["quality_gates"]["checks"] if not c["passed"]]
    assert [c["name"] for c in failed] == ["ruff"]
    assert "E501" in failed[0]["output"]

    feature = _feature(session_maker)
    assert feature.passes is False
    assert feature.in_progress is True  # Agent keeps the feature to fix it
    assert feature.failure_count == 1
    assert "ruff" in feature.failure_reason
    assert feature.quality_result["passed"] is False

    # A second blocked attempt increments the counter
    feature_mcp.feature_mark_passing(1)
    assert _feature(session_maker).failure_count == 2


def test_strict_mode_passes_when_checks_pass(mcp_project, monkeypatch):
    project_dir, session_maker = mcp_project
    _enable(monkeypatch)
    _set_checks(monkeypatch, [PASSING])

    result = json.loads(feature_mcp.feature_mark_passing(1))
    assert result["success"] is True
    assert result["quality_gates"]["passed"] is True

    feature = _feature(session_maker)
    assert feature.passes is True
    assert feature.in_progress is False
    assert feature.quality_result["checks"][0]["name"] == "tsc"


def test_non_strict_mode_warns_but_marks_passing(mcp_project, monkeypatch):
    project_dir, session_maker = mcp_project
    _enable(monkeypatch, "warn")
    _set_checks(monkeypatch, [FAILING])

    result = json.loads(feature_mcp.feature_mark_passing(1))
    assert result["success"] is True
    assert "warning" in result
    feature = _feature(session_maker)
    assert feature.passes is True
    assert feature.quality_result["passed"] is False


def test_mark_passing_already_passing_skips_checks(mcp_project, monkeypatch):
    project_dir, _ = mcp_project
    _enable(monkeypatch)
    _set_checks(monkeypatch, [PASSING])
    feature_mcp.feature_mark_passing(1)

    def boom(*args, **kwargs):
        raise AssertionError("checks should not run for an already-passing feature")

    monkeypatch.setattr(quality_gates, "detect_checks", boom)
    result = json.loads(feature_mcp.feature_mark_passing(1))
    assert "already passing" in result["error"]


def test_mark_passing_unknown_feature_with_gates(mcp_project, monkeypatch):
    project_dir, _ = mcp_project
    _enable(monkeypatch)
    result = json.loads(feature_mcp.feature_mark_passing(999))
    assert "not found" in result["error"]


def test_verify_quality_records_evidence(mcp_project, monkeypatch):
    _, session_maker = mcp_project
    _enable(monkeypatch)
    _set_checks(monkeypatch, [FAILING])

    result = json.loads(feature_mcp.feature_verify_quality(1))
    assert result["passed"] is False
    feature = _feature(session_maker)
    assert feature.quality_result["passed"] is False
    # Verifying alone is not a failed attempt
    assert feature.failure_count == 0
    assert feature.passes is False


def test_verify_quality_unknown_feature(mcp_project, monkeypatch):
    _enable(monkeypatch)
    result = json.loads(feature_mcp.feature_verify_quality(999))
    assert "not found" in result["error"]


def test_report_failure(mcp_project):
    _, session_maker = mcp_project

    result = json.loads(feature_mcp.feature_report_failure(1, "Login API returns 500"))
    assert result == {"feature_id": 1, "failure_count": 1, "failure_reason": "Login API returns 500"}

    result = json.loads(feature_mcp.feature_report_failure(1, "Still 500"))
    assert result["failure_count"] == 2

    feature = _feature(session_maker)
    assert feature.failure_reason == "Still 500"
    assert feature.in_progress is True
    assert feature.passes is False


def test_report_failure_unknown_feature(mcp_project):
    result = json.loads(feature_mcp.feature_report_failure(999, "x"))
    assert "not found" in result["error"]


def test_failure_reason_cleared_when_feature_passes(mcp_project, monkeypatch):
    _, session_maker = mcp_project
    _enable(monkeypatch)
    _set_checks(monkeypatch, [FAILING])
    feature_mcp.feature_mark_passing(1)
    assert _feature(session_maker).failure_reason is not None

    _set_checks(monkeypatch, [PASSING])
    assert json.loads(feature_mcp.feature_mark_passing(1))["success"] is True
    feature = _feature(session_maker)
    assert feature.failure_reason is None
    assert feature.failure_count == 1  # History is kept


def test_verify_quality_disabled_runs_nothing(mcp_project, monkeypatch):
    _, session_maker = mcp_project

    def boom(*args, **kwargs):
        raise AssertionError("checks must not run while gates are disabled")

    monkeypatch.setattr(quality_gates, "detect_checks", boom)
    result = json.loads(feature_mcp.feature_verify_quality(1))
    assert result == {"error": "Quality gates are not enabled for this project"}
    assert _feature(session_maker).quality_result is None


@pytest.mark.skipif(sys.platform == "win32", reason="uses an executable shell-style script")
def test_agent_written_tooling_never_runs_unless_trusted(mcp_project, tmp_path_factory):
    """Regression test for the QA finding on PR #334.

    An agent can create an executable node_modules/.bin/eslint, an eslint config
    and .autoforge/config.json enabling the gates. Without the trusted env
    switch, neither MCP tool may execute it.
    """
    project_dir, session_maker = mcp_project
    marker = tmp_path_factory.mktemp("outside") / "pwned"

    (project_dir / ".eslintrc.json").write_text("{}")
    bin_dir = project_dir / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    script = bin_dir / "eslint"
    script.write_text(f"#!{sys.executable}\nopen({str(marker)!r}, 'w').write('x')\n")
    script.chmod(0o755)
    _write_project_config(project_dir, {"enabled": True, "strict_mode": True})

    assert "not enabled" in json.loads(feature_mcp.feature_verify_quality(1))["error"]
    assert json.loads(feature_mcp.feature_mark_passing(1))["success"] is True
    assert not marker.exists()
    assert _feature(session_maker).quality_result is None
