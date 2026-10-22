"""
Tests for the Backlog state and Iterative Spec Roadmapping (maturity tags).

Covers:
- api/roadmap.py helpers (tag normalization, ordering, ready checks)
- Agent queue exclusion and maturity-based prioritization
- Database migration of the new columns
- REST endpoints: create, spec review, backlog, promote (with ready checks)
- MCP claim guardrail (Backlog features can never be claimed)
"""

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from api.dependency_resolver import compute_scheduling_scores, get_ready_features
from api.roadmap import (
    DEFAULT_MATURITY_ORDER,
    compute_readiness,
    failed_checks,
    maturity_rank,
    normalize_maturity,
    parse_maturity_order,
    ready_sort_key,
)


def _feature(fid, maturity=None, backlog=False, priority=1, deps=None, passes=False, in_progress=False):
    return {
        "id": fid,
        "priority": priority,
        "category": "core",
        "name": f"Feature {fid}",
        "description": "A sufficiently detailed description of the feature",
        "steps": ["Open the page", "Verify the result"],
        "passes": passes,
        "in_progress": in_progress,
        "dependencies": deps or [],
        "backlog": backlog,
        "maturity": maturity,
    }


# =============================================================================
# Helpers
# =============================================================================


class TestMaturityHelpers:
    def test_normalize_maturity(self):
        assert normalize_maturity("Limited Beta") == "limited_beta"
        assert normalize_maturity("limited-beta") == "limited_beta"
        assert normalize_maturity(" BETA ") == "beta"
        assert normalize_maturity("") is None
        assert normalize_maturity(None) is None
        with pytest.raises(ValueError):
            normalize_maturity("gamma")

    def test_parse_maturity_order(self):
        assert parse_maturity_order(None) == list(DEFAULT_MATURITY_ORDER)
        assert parse_maturity_order("") == list(DEFAULT_MATURITY_ORDER)
        assert parse_maturity_order("alpha,beta,limited_beta") == ["alpha", "beta", "limited_beta"]
        # Unknown/duplicate entries dropped, missing levels appended in default order
        assert parse_maturity_order("alpha,bogus,alpha") == ["alpha", "beta", "limited_beta"]

    def test_maturity_rank_untagged_last(self):
        order = ["beta", "limited_beta", "alpha"]
        assert maturity_rank("beta", order) == 0
        assert maturity_rank("alpha", order) == 2
        assert maturity_rank(None, order) == 3


class TestReadinessChecks:
    def test_ready_feature_passes_all_checks(self):
        f = _feature(1, maturity="beta", backlog=True)
        checks = compute_readiness(f, {1: f})
        assert failed_checks(checks) == []

    def test_unready_feature_reports_each_failure(self):
        dep = _feature(2, backlog=True)
        f = {
            **_feature(1, backlog=True, deps=[2, 99]),
            "description": "short",
            "steps": ["  "],
            "maturity": None,
        }
        failed = {c["id"] for c in failed_checks(compute_readiness(f, {1: f, 2: dep}))}
        assert failed == {"description", "acceptance_criteria", "maturity", "dependencies"}


# =============================================================================
# Agent queue: exclusion + prioritization
# =============================================================================


class TestAgentQueue:
    def test_backlog_excluded_from_ready(self):
        features = [_feature(1, maturity="beta", backlog=True), _feature(2)]
        ready_ids = [f["id"] for f in get_ready_features(features)]
        assert ready_ids == [2]

    def test_maturity_drives_order_default(self):
        features = [
            _feature(1, maturity="alpha", priority=1),
            _feature(2, priority=2),
            _feature(3, maturity="beta", priority=3),
            _feature(4, maturity="limited_beta", priority=4),
        ]
        ready_ids = [f["id"] for f in get_ready_features(features)]
        assert ready_ids == [3, 4, 1, 2]

    def test_maturity_order_configurable(self):
        features = [
            _feature(1, maturity="beta"),
            _feature(2, maturity="alpha"),
            _feature(3, maturity="limited_beta"),
        ]
        ready_ids = [f["id"] for f in get_ready_features(features, maturity_order=["alpha", "limited_beta", "beta"])]
        assert ready_ids == [2, 3, 1]

    def test_untagged_features_keep_scheduling_order(self):
        """Without tags, ordering is unchanged from the dependency-aware score."""
        features = [_feature(1, priority=5), _feature(2, priority=1), _feature(3, priority=3)]
        scores = compute_scheduling_scores(features)
        legacy = sorted(features, key=lambda f: (-scores[f["id"]], f["priority"], f["id"]))
        new = sorted(features, key=ready_sort_key(scores))
        assert [f["id"] for f in new] == [f["id"] for f in legacy]


# =============================================================================
# Database
# =============================================================================


class TestDatabase:
    def test_migration_adds_roadmap_columns(self):
        from api.database import create_database, dispose_engine
        from autoforge_paths import get_features_db_path

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            db_path = get_features_db_path(project_dir)
            db_path.parent.mkdir(parents=True, exist_ok=True)
            # Legacy schema without the new columns
            conn = sqlite3.connect(db_path)
            conn.execute(
                "CREATE TABLE features (id INTEGER PRIMARY KEY, priority INTEGER NOT NULL, "
                "category VARCHAR(100) NOT NULL, name VARCHAR(255) NOT NULL, description TEXT NOT NULL, "
                "steps JSON NOT NULL, passes BOOLEAN NOT NULL DEFAULT 0)"
            )
            conn.execute(
                "INSERT INTO features (priority, category, name, description, steps) "
                "VALUES (1, 'core', 'Legacy', 'Legacy feature', '[]')"
            )
            conn.commit()
            conn.close()

            try:
                create_database(project_dir)
                conn = sqlite3.connect(db_path)
                columns = {row[1] for row in conn.execute("PRAGMA table_info(features)")}
                assert {"backlog", "maturity", "spec_notes"} <= columns
                assert conn.execute("SELECT backlog, maturity FROM features").fetchone() == (0, None)
                conn.close()
            finally:
                dispose_engine(project_dir)


# =============================================================================
# REST API
# =============================================================================


@pytest.fixture
def project_dir():
    from api.database import dispose_engine

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        with patch("server.routers.features._get_project_path", return_value=path):
            yield path
        dispose_engine(path)


def _run(coro):
    return asyncio.run(coro)


class TestRestApi:
    def _create(self, **kwargs):
        from server.routers.features import create_feature
        from server.schemas import FeatureCreate

        data = {
            "category": "core",
            "name": "Feature",
            "description": "A sufficiently detailed description of the feature",
            "steps": ["Verify it works"],
            **kwargs,
        }
        return _run(create_feature("demo", FeatureCreate(**data)))

    def test_create_in_backlog_with_maturity(self, project_dir):
        from server.routers.features import list_features

        created = self._create(backlog=True, maturity="Limited Beta", spec_notes="Behind flag")
        assert created.backlog is True
        assert created.maturity == "limited_beta"
        assert created.ready is True

        listing = _run(list_features("demo"))
        assert [f.id for f in listing.backlog] == [created.id]
        assert listing.pending == []

    def test_promote_enforces_ready_checks(self, project_dir):
        from server.routers.features import list_features, promote_feature
        from server.schemas import PromoteRequest

        created = self._create(backlog=True)  # no maturity tag -> not ready
        assert created.ready is False

        with pytest.raises(HTTPException) as exc:
            _run(promote_feature("demo", created.id, PromoteRequest()))
        assert exc.value.status_code == 409
        assert [c["id"] for c in exc.value.detail["failed_checks"]] == ["maturity"]

        # Explicit human override
        promoted = _run(promote_feature("demo", created.id, PromoteRequest(force=True)))
        assert promoted.backlog is False
        assert [f.id for f in _run(list_features("demo")).pending] == [created.id]

    def test_spec_review_then_promote(self, project_dir):
        from server.routers.features import promote_feature, review_feature_spec
        from server.schemas import PromoteRequest, SpecReviewRequest

        created = self._create(backlog=True)
        reviewed = _run(review_feature_spec(
            "demo", created.id, SpecReviewRequest(maturity="beta", notes="Don't break login")
        ))
        assert reviewed.maturity == "beta"
        assert reviewed.spec_notes == "Don't break login"
        assert reviewed.ready is True

        promoted = _run(promote_feature("demo", created.id, PromoteRequest()))
        assert promoted.backlog is False

    def test_move_to_backlog_rules(self, project_dir):
        from api.database import Feature, create_database
        from server.routers.features import move_feature_to_backlog

        created = self._create()
        moved = _run(move_feature_to_backlog("demo", created.id))
        assert moved.backlog is True

        # In-progress features cannot be parked
        other = self._create()
        _, SessionLocal = create_database(project_dir)
        with SessionLocal() as session:
            session.query(Feature).filter(Feature.id == other.id).update({"in_progress": True})
            session.commit()
        with pytest.raises(HTTPException) as exc:
            _run(move_feature_to_backlog("demo", other.id))
        assert exc.value.status_code == 409

    def test_update_can_clear_maturity(self, project_dir):
        from server.routers.features import update_feature
        from server.schemas import FeatureUpdate

        created = self._create(maturity="alpha")
        unchanged = _run(update_feature("demo", created.id, FeatureUpdate(name="Renamed")))
        assert unchanged.maturity == "alpha"
        cleared = _run(update_feature("demo", created.id, FeatureUpdate(maturity=None)))
        assert cleared.maturity is None

    def test_graph_reports_backlog_status(self, project_dir):
        from server.routers.features import get_dependency_graph

        created = self._create(backlog=True, maturity="alpha")
        graph = _run(get_dependency_graph("demo"))
        node = next(n for n in graph.nodes if n.id == created.id)
        assert node.status == "backlog"
        assert node.maturity == "alpha"

    def test_mcp_cannot_claim_backlog_feature(self, project_dir):
        import mcp_server.feature_mcp as feature_mcp
        from api.database import create_database

        created = self._create(backlog=True, maturity="beta")
        _, SessionLocal = create_database(project_dir)
        with patch.object(feature_mcp, "_session_maker", SessionLocal):
            claim = json.loads(feature_mcp.feature_claim_and_get(created.id))
            mark = json.loads(feature_mcp.feature_mark_in_progress(created.id))
            ready = json.loads(feature_mcp.feature_get_ready(10))
        assert "Backlog" in claim["error"]
        assert "Backlog" in mark["error"]
        assert ready["total_ready"] == 0


class TestSettingsSchema:
    def test_maturity_order_normalized_and_validated(self):
        from pydantic import ValidationError

        from server.schemas import SettingsUpdate

        update = SettingsUpdate(maturity_order=["Limited Beta", "alpha", "BETA"])
        assert update.maturity_order == ["limited_beta", "alpha", "beta"]
        with pytest.raises(ValidationError):
            SettingsUpdate(maturity_order=["alpha", "alpha", "beta"])
        with pytest.raises(ValidationError):
            SettingsUpdate(maturity_order=["alpha", "gamma", "beta"])
