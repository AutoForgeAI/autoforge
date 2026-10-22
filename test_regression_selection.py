#!/usr/bin/env python3
"""
Regression Test Selection Tests
===============================

Verifies that testing agents cover every passing feature before re-testing
any of them (issue #20), using the persisted ``regression_count`` column.
Run with: python -m pytest test_regression_selection.py
"""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import text

from api.database import Feature, create_database, dispose_engine, get_database_path
from parallel_orchestrator import ParallelOrchestrator


def _add_features(project_dir: Path, specs: list[dict]) -> None:
    _, session_maker = create_database(project_dir)
    session = session_maker()
    try:
        for i, spec in enumerate(specs, start=1):
            session.add(Feature(
                id=i,
                priority=i,
                category="test",
                name=f"Feature {i}",
                description="desc",
                steps=["step"],
                passes=spec.get("passes", True),
                in_progress=spec.get("in_progress", False),
                dependencies=spec.get("dependencies"),
            ))
        session.commit()
    finally:
        session.close()


def _regression_counts(project_dir: Path) -> dict[int, int]:
    _, session_maker = create_database(project_dir)
    session = session_maker()
    try:
        return {f.id: f.regression_count for f in session.query(Feature).all()}
    finally:
        session.close()


@pytest.fixture
def project_dir(tmp_path):
    yield tmp_path
    dispose_engine(tmp_path)


def test_batches_cover_all_features_before_repeating(project_dir):
    _add_features(project_dir, [{} for _ in range(10)])
    orch = ParallelOrchestrator(project_dir, testing_batch_size=3)

    seen: list[int] = []
    for _ in range(4):  # 4 batches of 3 = 12 picks across 10 features
        seen.extend(orch._get_test_batch(3))

    # The first 10 picks must be all distinct features (no duplicates).
    assert sorted(seen[:10]) == list(range(1, 11))
    counts = _regression_counts(project_dir)
    assert sum(counts.values()) == 12
    assert max(counts.values()) - min(counts.values()) <= 1


def test_selection_persists_across_orchestrator_restarts(project_dir):
    _add_features(project_dir, [{} for _ in range(6)])

    first = ParallelOrchestrator(project_dir)._get_test_batch(3)
    # A fresh orchestrator (e.g. after restart) must continue with the rest.
    second = ParallelOrchestrator(project_dir)._get_test_batch(3)

    assert set(first).isdisjoint(second)
    assert sorted(first + second) == list(range(1, 7))


def test_skips_non_passing_and_in_progress_features(project_dir):
    _add_features(project_dir, [
        {"passes": True},
        {"passes": False},
        {"passes": True, "in_progress": True},
        {"passes": True},
    ])
    orch = ParallelOrchestrator(project_dir)

    assert sorted(orch._get_test_batch(5)) == [1, 4]
    counts = _regression_counts(project_dir)
    assert counts[2] == 0 and counts[3] == 0


def test_high_impact_features_first_within_same_count(project_dir):
    # Features 2 and 3 depend on feature 1, so 1 is highest impact.
    _add_features(project_dir, [
        {},
        {"dependencies": [1]},
        {"dependencies": [1]},
        {},
    ])
    orch = ParallelOrchestrator(project_dir)

    assert orch._get_test_batch(1) == [1]


def test_random_passing_feature_uses_least_tested(project_dir):
    _add_features(project_dir, [{} for _ in range(4)])
    orch = ParallelOrchestrator(project_dir)

    picks = [orch._get_random_passing_feature() for _ in range(4)]
    assert sorted(p for p in picks if p is not None) == [1, 2, 3, 4]


def test_migration_adds_regression_count_to_legacy_db(project_dir):
    db_path = get_database_path(project_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE features (id INTEGER PRIMARY KEY, priority INTEGER NOT NULL, "
        "category VARCHAR(100) NOT NULL, name VARCHAR(255) NOT NULL, description TEXT NOT NULL, "
        "steps JSON NOT NULL, passes BOOLEAN NOT NULL)"
    )
    conn.execute(
        "INSERT INTO features (id, priority, category, name, description, steps, passes) "
        "VALUES (1, 1, 'c', 'n', 'd', '[]', 1)"
    )
    conn.commit()
    conn.close()

    engine, _ = create_database(project_dir)
    with engine.connect() as c:
        columns = [row[1] for row in c.execute(text("PRAGMA table_info(features)")).fetchall()]
    assert "regression_count" in columns
    assert _regression_counts(project_dir) == {1: 0}
