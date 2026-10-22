"""
Regression Test Selection Tests
===============================

Tests for regression-testing feature selection in the parallel orchestrator.
Every passing feature must be tested once before any feature is re-tested,
tracked via the persistent ``regression_count`` column (issue #20).

Run with: python -m pytest test_regression_selection.py -v
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from api.database import Feature, dispose_engine
from parallel_orchestrator import ParallelOrchestrator


class RegressionSelectionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)
        self.orch = ParallelOrchestrator(self.project_dir, max_concurrency=3)

    def tearDown(self):
        dispose_engine(self.project_dir)
        self._tmp.cleanup()

    def _add_features(self, count: int, passes: bool = True, dependencies=None) -> list[int]:
        session = self.orch.get_session()
        try:
            features = [
                Feature(
                    priority=i,
                    category="test",
                    name=f"Feature {i}",
                    description="desc",
                    steps=["step"],
                    passes=passes,
                    dependencies=dependencies,
                )
                for i in range(count)
            ]
            session.add_all(features)
            session.commit()
            return [int(f.id) for f in features]
        finally:
            session.close()

    def _regression_counts(self) -> dict[int, int]:
        session = self.orch.get_session()
        try:
            return {int(f.id): int(f.regression_count) for f in session.query(Feature).all()}
        finally:
            session.close()

    def test_all_features_covered_before_any_repeat(self):
        ids = self._add_features(10)

        tested: list[int] = []
        # 4 batches of 3 = 12 picks; first 10 must be unique
        for _ in range(4):
            tested.extend(self.orch._get_test_batch(3))

        self.assertEqual(sorted(tested[:10]), sorted(ids))
        counts = self._regression_counts()
        self.assertTrue(all(1 <= c <= 2 for c in counts.values()))
        self.assertEqual(sum(counts.values()), 12)

    def test_coverage_persists_across_orchestrator_restarts(self):
        ids = self._add_features(6)
        first = self.orch._get_test_batch(3)

        # A fresh orchestrator must continue with the untested features
        fresh = ParallelOrchestrator(self.project_dir, max_concurrency=3)
        second = fresh._get_test_batch(3)

        self.assertEqual(sorted(first + second), sorted(ids))

    def test_failing_features_not_selected(self):
        passing = self._add_features(2, passes=True)
        self._add_features(3, passes=False)

        self.assertEqual(sorted(self.orch._get_test_batch(5)), sorted(passing))

    def test_features_assigned_to_running_agents_are_excluded(self):
        ids = self._add_features(4)
        self.orch._testing_batch_ids[12345] = ids[:3]

        self.assertEqual(self.orch._get_test_batch(3), [ids[3]])

    def test_high_impact_features_preferred_within_same_count(self):
        base = self._add_features(3)
        # Two features depend on base[0], making it the highest-impact feature
        self._add_features(2, dependencies=[base[0]])

        self.assertEqual(self.orch._get_test_batch(1), [base[0]])

    def test_no_passing_features_returns_empty(self):
        self._add_features(3, passes=False)
        self.assertEqual(self.orch._get_test_batch(3), [])


class RegressionCountMigrationTests(unittest.TestCase):
    def test_legacy_database_gets_regression_count_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            db_dir = project_dir / ".autoforge"
            db_dir.mkdir()
            conn = sqlite3.connect(db_dir / "features.db")
            conn.execute(
                "CREATE TABLE features (id INTEGER PRIMARY KEY, priority INTEGER NOT NULL, "
                "category VARCHAR(100) NOT NULL, name VARCHAR(255) NOT NULL, description TEXT NOT NULL, "
                "steps JSON NOT NULL, passes BOOLEAN NOT NULL)"
            )
            conn.execute(
                "INSERT INTO features (priority, category, name, description, steps, passes) "
                "VALUES (1, 'c', 'n', 'd', '[\"s\"]', 1)"
            )
            conn.commit()
            conn.close()

            try:
                orch = ParallelOrchestrator(project_dir, max_concurrency=1)
                self.assertEqual(orch._get_test_batch(3), [1])
                session = orch.get_session()
                try:
                    self.assertEqual(session.query(Feature).one().regression_count, 1)
                finally:
                    session.close()
            finally:
                dispose_engine(project_dir)


if __name__ == "__main__":
    unittest.main()
