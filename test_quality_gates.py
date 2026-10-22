"""
Quality Gates Tests
===================

Tests for quality_gates.py (config loading, tool detection, running checks)
and the quality gate integration in the feature MCP server.

Run with: python -m pytest test_quality_gates.py
"""

import json
import stat
import sys
from pathlib import Path

import pytest

import quality_gates
from quality_gates import QualityGateConfig, detect_checks, load_config, run_quality_checks

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="uses POSIX shell scripts as fake tools")


def _write_config(project_dir: Path, section: dict) -> None:
    autoforge_dir = project_dir / ".autoforge"
    autoforge_dir.mkdir(parents=True, exist_ok=True)
    (autoforge_dir / "config.json").write_text(json.dumps({"quality_gates": section}))


def _fake_tool(path: Path, exit_code: int, output: str = "") -> None:
    """Create an executable script standing in for a linter/type checker."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!/bin/sh\necho '{output}'\nexit {exit_code}\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _js_project(project_dir: Path, eslint_exit: int = 0, tsc_exit: int = 0) -> None:
    (project_dir / "package.json").write_text("{}")
    (project_dir / "eslint.config.js").write_text("export default [];")
    (project_dir / "tsconfig.json").write_text("{}")
    _fake_tool(project_dir / "node_modules" / ".bin" / "eslint", eslint_exit, "eslint output")
    _fake_tool(project_dir / "node_modules" / ".bin" / "tsc", tsc_exit, "tsc output")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_missing_config_is_disabled(self, tmp_path):
        assert load_config(tmp_path) == QualityGateConfig()
        assert load_config(tmp_path).enabled is False

    def test_malformed_config_is_disabled(self, tmp_path):
        (tmp_path / ".autoforge").mkdir()
        (tmp_path / ".autoforge" / "config.json").write_text("{not json")
        assert load_config(tmp_path).enabled is False

    def test_enabled_defaults_to_strict(self, tmp_path):
        _write_config(tmp_path, {"enabled": True})
        config = load_config(tmp_path)
        assert config.enabled is True
        assert config.strict_mode is True
        assert config.lint is True
        assert config.type_check is True

    def test_full_config(self, tmp_path):
        _write_config(tmp_path, {
            "enabled": True,
            "strict_mode": False,
            "checks": {"lint": False, "type_check": True},
            "timeout_seconds": 30,
        })
        config = load_config(tmp_path)
        assert config.strict_mode is False
        assert config.lint is False
        assert config.type_check is True
        assert config.timeout_seconds == 30

    def test_truthy_non_bool_does_not_enable(self, tmp_path):
        _write_config(tmp_path, {"enabled": "yes"})
        assert load_config(tmp_path).enabled is False

    def test_invalid_timeout_falls_back(self, tmp_path):
        _write_config(tmp_path, {"enabled": True, "timeout_seconds": -5})
        assert load_config(tmp_path).timeout_seconds == quality_gates.DEFAULT_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

class TestDetectChecks:
    def test_empty_project(self, tmp_path):
        assert detect_checks(tmp_path) == []

    def test_js_project(self, tmp_path):
        _js_project(tmp_path)
        names = [(c.name, c.kind) for c in detect_checks(tmp_path)]
        assert names == [("eslint", "lint"), ("tsc", "type_check")]

    def test_tsc_build_mode_for_project_references(self, tmp_path):
        _js_project(tmp_path)
        (tmp_path / "tsconfig.json").write_text('{"files": [], "references": [{"path": "./tsconfig.app.json"}]}')
        tsc = next(c for c in detect_checks(tmp_path) if c.name == "tsc")
        assert tsc.command[1:] == ["-b", "--noEmit"]

    def test_configured_but_not_installed_is_skipped(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "eslint.config.js").write_text("export default [];")
        (tmp_path / "tsconfig.json").write_text("{}")
        assert detect_checks(tmp_path) == []

    def test_installed_but_not_configured_is_skipped(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        _fake_tool(tmp_path / "node_modules" / ".bin" / "eslint", 0)
        assert detect_checks(tmp_path) == []

    def test_biome_preferred_over_eslint(self, tmp_path):
        _js_project(tmp_path)
        (tmp_path / "biome.json").write_text("{}")
        _fake_tool(tmp_path / "node_modules" / ".bin" / "biome", 0)
        names = [c.name for c in detect_checks(tmp_path)]
        assert names == ["biome", "tsc"]

    def test_python_project_uses_project_venv(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n\n[tool.mypy]\nstrict = true\n")
        _fake_tool(tmp_path / ".venv" / "bin" / "ruff", 0)
        _fake_tool(tmp_path / ".venv" / "bin" / "mypy", 0)
        checks = detect_checks(tmp_path)
        assert [c.name for c in checks] == ["ruff", "mypy"]
        assert checks[0].command[0] == str(tmp_path / ".venv" / "bin" / "ruff")

    def test_flake8_from_setup_cfg(self, tmp_path):
        (tmp_path / "setup.cfg").write_text("[flake8]\nmax-line-length = 120\n")
        _fake_tool(tmp_path / "venv" / "bin" / "flake8", 0)
        assert [c.name for c in detect_checks(tmp_path)] == ["flake8"]


# ---------------------------------------------------------------------------
# Running checks
# ---------------------------------------------------------------------------

class TestRunQualityChecks:
    def test_all_pass(self, tmp_path):
        _js_project(tmp_path)
        report = run_quality_checks(tmp_path, QualityGateConfig(enabled=True))
        assert report.passed is True
        assert [c.passed for c in report.checks] == [True, True]
        assert report.checks[0].output == "eslint output"
        assert report.checks[0].command == "eslint ."

    def test_failure_is_reported(self, tmp_path):
        _js_project(tmp_path, tsc_exit=2)
        report = run_quality_checks(tmp_path, QualityGateConfig(enabled=True))
        assert report.passed is False
        assert [c.name for c in report.failed_checks] == ["tsc"]
        assert report.checks[1].returncode == 2
        assert "tsc: FAILED" in report.summary()
        assert quality_gates.format_failure_reason(report) == "Quality gate failed: tsc"

    def test_disabled_check_kinds_are_skipped(self, tmp_path):
        _js_project(tmp_path, tsc_exit=1)
        report = run_quality_checks(tmp_path, QualityGateConfig(enabled=True, type_check=False))
        assert report.passed is True
        assert [c.name for c in report.checks] == ["eslint"]

    def test_no_tools_passes(self, tmp_path):
        report = run_quality_checks(tmp_path, QualityGateConfig(enabled=True))
        assert report.passed is True
        assert report.checks == []

    def test_timeout_fails_check(self, tmp_path):
        _js_project(tmp_path)
        (tmp_path / "node_modules" / ".bin" / "eslint").write_text("#!/bin/sh\nsleep 5\n")
        report = run_quality_checks(tmp_path, QualityGateConfig(enabled=True, timeout_seconds=1, type_check=False))
        assert report.passed is False
        assert "Timed out" in report.checks[0].output

    def test_output_is_truncated(self, tmp_path):
        _js_project(tmp_path)
        (tmp_path / "node_modules" / ".bin" / "eslint").write_text(
            "#!/bin/sh\nhead -c 20000 /dev/zero | tr '\\0' 'x'\nexit 1\n"
        )
        report = run_quality_checks(tmp_path, QualityGateConfig(enabled=True, type_check=False))
        assert len(report.checks[0].output) <= quality_gates.MAX_OUTPUT_CHARS + 50


# ---------------------------------------------------------------------------
# Feature MCP integration
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp(tmp_path, monkeypatch):
    """Feature MCP module wired to a fresh database in tmp_path with one feature."""
    from api.database import Feature, create_database
    from mcp_server import feature_mcp

    engine, session_maker = create_database(tmp_path)
    monkeypatch.setattr(feature_mcp, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(feature_mcp, "_session_maker", session_maker)

    session = session_maker()
    session.add(Feature(priority=1, category="core", name="Login", description="d", steps=["s"], in_progress=True))
    session.commit()
    session.close()

    yield feature_mcp

    from api.database import dispose_engine
    dispose_engine(tmp_path)


def _feature(mcp_module) -> dict:
    feature: dict = json.loads(mcp_module.feature_get_by_id(1))
    return feature


class TestFeatureMcpIntegration:
    def test_gates_disabled_marks_passing_without_checks(self, mcp, tmp_path):
        _js_project(tmp_path, eslint_exit=1)
        result = json.loads(mcp.feature_mark_passing(1))
        assert result["success"] is True
        assert "quality_gate" not in result
        assert _feature(mcp)["passes"] is True
        assert _feature(mcp)["quality_result"] is None

    def test_strict_mode_blocks_failing_feature(self, mcp, tmp_path):
        _js_project(tmp_path, eslint_exit=1)
        _write_config(tmp_path, {"enabled": True})

        result = json.loads(mcp.feature_mark_passing(1))
        assert "Quality gate failed" in result["error"]
        assert result["quality_gate"]["passed"] is False

        feature = _feature(mcp)
        assert feature["passes"] is False
        assert feature["in_progress"] is True
        assert feature["failure_count"] == 1
        assert feature["failure_reason"] == "Quality gate failed: eslint"
        assert feature["quality_result"]["passed"] is False

    def test_strict_mode_passes_after_fix(self, mcp, tmp_path):
        _js_project(tmp_path, eslint_exit=1)
        _write_config(tmp_path, {"enabled": True})
        json.loads(mcp.feature_mark_passing(1))

        _fake_tool(tmp_path / "node_modules" / ".bin" / "eslint", 0)
        result = json.loads(mcp.feature_mark_passing(1))
        assert result["success"] is True
        assert result["quality_gate"]["passed"] is True

        feature = _feature(mcp)
        assert feature["passes"] is True
        assert feature["in_progress"] is False
        assert feature["failure_reason"] is None
        assert feature["failure_count"] == 1  # history is kept
        assert feature["quality_result"]["passed"] is True

    def test_non_strict_mode_warns(self, mcp, tmp_path):
        _js_project(tmp_path, tsc_exit=1)
        _write_config(tmp_path, {"enabled": True, "strict_mode": False})

        result = json.loads(mcp.feature_mark_passing(1))
        assert result["success"] is True
        assert result["quality_gate"]["passed"] is False
        assert "warning" in result
        feature = _feature(mcp)
        assert feature["passes"] is True
        assert feature["quality_result"]["passed"] is False

    def test_already_passing_skips_checks(self, mcp, tmp_path):
        _write_config(tmp_path, {"enabled": True})
        mcp.feature_mark_passing(1)
        result = json.loads(mcp.feature_mark_passing(1))
        assert "already passing" in result["error"]

    def test_verify_quality_stores_evidence(self, mcp, tmp_path):
        _js_project(tmp_path, tsc_exit=1)
        _write_config(tmp_path, {"enabled": True})
        result = json.loads(mcp.feature_verify_quality(1))
        assert result["passed"] is False
        assert [c["name"] for c in result["checks"]] == ["eslint", "tsc"]
        assert _feature(mcp)["quality_result"]["summary"] == result["summary"]
        # Verifying never changes status
        assert _feature(mcp)["passes"] is False

    def test_verify_quality_without_feature(self, mcp, tmp_path):
        _write_config(tmp_path, {"enabled": True})
        result = json.loads(mcp.feature_verify_quality())
        assert result["passed"] is True
        assert result["checks"] == []

    def test_verify_quality_unknown_feature(self, mcp, tmp_path):
        _write_config(tmp_path, {"enabled": True})
        assert "not found" in json.loads(mcp.feature_verify_quality(999))["error"]

    @pytest.mark.parametrize("section", [None, {"enabled": False}])
    def test_verify_quality_disabled_runs_nothing(self, mcp, tmp_path, monkeypatch, section):
        _js_project(tmp_path, eslint_exit=1)
        if section is not None:
            _write_config(tmp_path, section)

        def fail(*args, **kwargs):
            raise AssertionError("quality tooling must not run when gates are disabled")

        monkeypatch.setattr(quality_gates, "detect_checks", fail)
        monkeypatch.setattr(quality_gates, "_run_check", fail)
        monkeypatch.setattr(quality_gates.subprocess, "run", fail)

        for feature_id in (1, None):
            result = json.loads(mcp.feature_verify_quality(feature_id))
            assert result["error"] == (
                "Quality gates are not enabled for this project (.autoforge/config.json)"
            )
        assert _feature(mcp)["quality_result"] is None

    def test_mark_failing_tracks_reason_and_count(self, mcp):
        mcp.feature_mark_failing(1, reason="Login button does nothing")
        mcp.feature_mark_failing(1)
        feature = _feature(mcp)
        assert feature["failure_count"] == 2
        assert feature["failure_reason"] == "Login button does nothing"


def test_migration_adds_columns_to_existing_db(tmp_path):
    """Databases created before quality gates get the new columns."""
    import sqlite3

    from api.database import create_database, dispose_engine

    db_dir = tmp_path / ".autoforge"
    db_dir.mkdir()
    conn = sqlite3.connect(db_dir / "features.db")
    conn.execute(
        "CREATE TABLE features (id INTEGER PRIMARY KEY, priority INTEGER NOT NULL, category VARCHAR(100) NOT NULL, "
        "name VARCHAR(255) NOT NULL, description TEXT NOT NULL, steps JSON NOT NULL, passes BOOLEAN NOT NULL)"
    )
    conn.execute("INSERT INTO features VALUES (1, 1, 'c', 'n', 'd', '[]', 0)")
    conn.commit()
    conn.close()

    create_database(tmp_path)
    dispose_engine(tmp_path)

    conn = sqlite3.connect(db_dir / "features.db")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(features)")}
    row = conn.execute("SELECT failure_count, failure_reason, quality_result FROM features").fetchone()
    conn.close()
    assert {"quality_result", "failure_reason", "failure_count"} <= columns
    assert row == (0, None, None)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", *sys.argv[1:]]))


class TestClientToolExposure:
    """feature_verify_quality is only offered to agents when gates are enabled."""

    TOOL = "mcp__features__feature_verify_quality"

    def test_hidden_without_config(self, tmp_path):
        from client import get_feature_tools
        for agent_type in ("coding", "testing", "initializer"):
            assert self.TOOL not in get_feature_tools(agent_type, tmp_path)

    def test_hidden_when_disabled(self, tmp_path):
        from client import get_feature_tools
        _write_config(tmp_path, {"enabled": False})
        assert self.TOOL not in get_feature_tools("coding", tmp_path)
        assert self.TOOL not in get_feature_tools("testing", tmp_path)

    def test_exposed_when_enabled(self, tmp_path):
        from client import get_feature_tools
        _write_config(tmp_path, {"enabled": True})
        assert self.TOOL in get_feature_tools("coding", tmp_path)
        assert self.TOOL in get_feature_tools("testing", tmp_path)
        assert self.TOOL not in get_feature_tools("initializer", tmp_path)
