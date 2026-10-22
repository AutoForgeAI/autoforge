"""
Backlog & Maturity Tag Tests
============================

Tests for the backlog state, maturity-tag prioritization and ready checks
(issue #56).

Run with: python -m pytest test_backlog_maturity.py -v
"""

import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

from api.database import Feature, create_database, dispose_engine
from api.dependency_resolver import build_graph_data, get_ready_features
from api.maturity import (
    DEFAULT_MATURITY_ORDER,
    check_readiness,
    is_schedulable,
    maturity_rank,
    parse_maturity_order,
    sort_build_queue,
)


def _feature(fid, **kw):
    base = {
        "id": fid,
        "priority": fid,
        "category": "core",
        "name": f"F{fid}",
        "description": "desc",
        "steps": ["step"],
        "passes": False,
        "in_progress": False,
        "needs_human_input": False,
        "dependencies": [],
        "backlog": False,
        "maturity": None,
    }
    base.update(kw)
    return base


class TestMaturityOrder(unittest.TestCase):
    def test_default_order(self):
        self.assertEqual(parse_maturity_order(None), ["beta", "limited_beta", "alpha"])

    def test_custom_order_is_normalized_and_completed(self):
        self.assertEqual(parse_maturity_order("alpha, Limited Beta"), ["alpha", "limited_beta", "beta"])
        self.assertEqual(parse_maturity_order("bogus,alpha,alpha"), ["alpha", "beta", "limited_beta"])

    def test_untagged_ranks_last(self):
        order = list(DEFAULT_MATURITY_ORDER)
        self.assertLess(maturity_rank({"maturity": "alpha"}, order), maturity_rank({"maturity": None}, order))
        self.assertLess(maturity_rank({"maturity": "beta"}, order), maturity_rank({"maturity": "alpha"}, order))

    def test_sort_build_queue_maturity_before_scores(self):
        feats = [_feature(1, maturity="alpha"), _feature(2, maturity="beta"), _feature(3)]
        # Feature 1 has the best scheduling score but alpha ranks below beta
        sort_build_queue(feats, {1: 1000.0, 2: 0.0, 3: 500.0})
        self.assertEqual([f["id"] for f in feats], [2, 1, 3])

    def test_sort_build_queue_custom_order(self):
        feats = [_feature(1, maturity="alpha"), _feature(2, maturity="beta")]
        sort_build_queue(feats, {}, ["alpha", "limited_beta", "beta"])
        self.assertEqual([f["id"] for f in feats], [1, 2])

    def test_untagged_ordering_unchanged(self):
        feats = [_feature(1), _feature(2), _feature(3)]
        sort_build_queue(feats, {1: 1.0, 2: 3.0, 3: 2.0})
        self.assertEqual([f["id"] for f in feats], [2, 3, 1])


class TestBacklogExclusion(unittest.TestCase):
    def test_is_schedulable(self):
        self.assertTrue(is_schedulable(_feature(1)))
        self.assertFalse(is_schedulable(_feature(1, backlog=True)))
        self.assertFalse(is_schedulable(_feature(1, needs_human_input=True)))

    def test_resolver_skips_backlog(self):
        feats = [_feature(1, backlog=True, maturity="beta"), _feature(2, maturity="alpha"), _feature(3)]
        ready = get_ready_features(feats)
        self.assertEqual([f["id"] for f in ready], [2, 3])

    def test_graph_status_backlog(self):
        graph = build_graph_data([_feature(1, backlog=True)])
        self.assertEqual(graph["nodes"][0]["status"], "backlog")


class TestOrchestratorQueue(unittest.TestCase):
    def setUp(self):
        from parallel_orchestrator import ParallelOrchestrator

        self.tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.tmp.name)
        with patch("parallel_orchestrator.get_maturity_order", return_value=["beta", "limited_beta", "alpha"]):
            self.orch = ParallelOrchestrator(self.project_dir, max_concurrency=1)

    def tearDown(self):
        dispose_engine(self.project_dir)
        self.tmp.cleanup()

    def test_ready_features_skip_backlog_and_sort_by_maturity(self):
        feats = [
            _feature(1, maturity="alpha"),
            _feature(2, backlog=True, maturity="beta"),
            _feature(3, maturity="beta"),
            _feature(4),
        ]
        ready = self.orch.get_ready_features(feats, {})
        self.assertEqual([f["id"] for f in ready], [3, 1, 4])

    def test_backlog_does_not_block_completion(self):
        feats = [_feature(1, passes=True), _feature(2, backlog=True)]
        self.assertTrue(self.orch.get_all_complete(feats))
        self.assertFalse(self.orch.get_all_complete(feats + [_feature(3)]))


class TestReadinessChecks(unittest.TestCase):
    def _failed(self, feature, all_features=None):
        checks = check_readiness(feature, all_features or [feature])
        return {c["id"] for c in checks if not c["passed"]}

    def test_complete_feature_is_ready(self):
        self.assertEqual(self._failed(_feature(1, maturity="beta")), set())

    def test_missing_fields(self):
        f = _feature(1, description="  ", steps=[], maturity=None)
        self.assertEqual(self._failed(f), {"description", "acceptance_criteria", "maturity"})

    def test_dependency_checks(self):
        dep = _feature(2, backlog=True)
        f = _feature(1, maturity="beta", dependencies=[2, 99])
        self.assertEqual(self._failed(f, [f, dep]), {"dependencies_exist", "dependencies_committed"})


class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.tmp.name)

    def tearDown(self):
        dispose_engine(self.project_dir)
        self.tmp.cleanup()

    def test_migration_adds_columns_to_legacy_db(self):
        db_path = self.project_dir / ".autoforge" / "features.db"
        db_path.parent.mkdir(parents=True)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE features (id INTEGER PRIMARY KEY, priority INTEGER NOT NULL, "
            "category VARCHAR(100) NOT NULL, name VARCHAR(255) NOT NULL, description TEXT NOT NULL, "
            "steps JSON NOT NULL, passes BOOLEAN NOT NULL)"
        )
        conn.execute("INSERT INTO features VALUES (1, 1, 'c', 'n', 'd', '[]', 0)")
        conn.commit()
        conn.close()

        _, session_maker = create_database(self.project_dir)
        session = session_maker()
        try:
            f = session.query(Feature).first()
            self.assertFalse(f.backlog)
            self.assertIsNone(f.maturity)
            self.assertEqual(f.to_dict()["backlog"], False)
        finally:
            session.close()


class TestFeatureRouter(unittest.TestCase):
    """Exercise the router handlers directly against a temp project database."""

    def setUp(self):
        from server.routers import features as router

        self.router = router
        self.tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.tmp.name)
        (self.project_dir / ".autoforge").mkdir()
        _, session_maker = create_database(self.project_dir)
        session = session_maker()
        session.add_all([
            Feature(id=1, priority=1, category="c", name="ready", description="d", steps=["s"],
                    passes=False, in_progress=False, backlog=True, maturity="beta"),
            Feature(id=2, priority=2, category="c", name="unspecified", description="d", steps=[],
                    passes=False, in_progress=False, backlog=True),
            Feature(id=3, priority=3, category="c", name="pending", description="d", steps=["s"],
                    passes=False, in_progress=False),
        ])
        session.commit()
        session.close()
        self.patcher = patch.object(router, "_get_project_path", return_value=self.project_dir)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        dispose_engine(self.project_dir)
        self.tmp.cleanup()

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_list_separates_backlog(self):
        result = self.run_async(self.router.list_features("proj"))
        self.assertEqual([f.id for f in result.backlog], [1, 2])
        self.assertEqual([f.id for f in result.pending], [3])

    def test_promote_ready_feature(self):
        result = self.run_async(self.router.promote_feature("proj", 1))
        self.assertFalse(result.backlog)

    def test_promote_rejects_unready_feature(self):
        with self.assertRaises(HTTPException) as ctx:
            self.run_async(self.router.promote_feature("proj", 2))
        self.assertEqual(ctx.exception.status_code, 409)
        failed = {c["id"] for c in ctx.exception.detail["checks"] if not c["passed"]}
        self.assertEqual(failed, {"acceptance_criteria", "maturity"})

    def test_promote_force_override(self):
        req = self.router.FeaturePromoteRequest(force=True)
        result = self.run_async(self.router.promote_feature("proj", 2, req))
        self.assertFalse(result.backlog)

    def test_move_to_backlog_and_tag(self):
        result = self.run_async(self.router.move_feature_to_backlog("proj", 3))
        self.assertTrue(result.backlog)
        update = self.router.FeatureUpdate(maturity="limited_beta", spec_notes="  behind flag ")
        result = self.run_async(self.router.update_feature("proj", 3, update))
        self.assertEqual(result.maturity, "limited_beta")
        self.assertEqual(result.spec_notes, "behind flag")
        # Explicit null clears the tag; omitting it leaves it alone
        result = self.run_async(self.router.update_feature("proj", 3, self.router.FeatureUpdate(name="x")))
        self.assertEqual(result.maturity, "limited_beta")
        result = self.run_async(self.router.update_feature("proj", 3, self.router.FeatureUpdate(maturity=None)))
        self.assertIsNone(result.maturity)

    def test_readiness_endpoint(self):
        result = self.run_async(self.router.get_feature_readiness("proj", 2))
        self.assertFalse(result.ready)


if __name__ == "__main__":
    unittest.main()
