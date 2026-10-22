"""
Unit tests for editing features via PATCH /api/projects/{name}/features/{id}.

Covers editing completed features (issue #25) and the optional `reopen` flag.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.database import Feature, create_database
from server.routers import features as features_router
from server.schemas import FeatureUpdate


class TestUpdateFeature(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)
        _, SessionLocal = create_database(self.project_dir)
        with SessionLocal() as session:
            session.add(Feature(
                id=1, priority=1, category="UI", name="Done feature",
                description="Original", steps=["a"], passes=True, in_progress=False,
            ))
            session.add(Feature(
                id=2, priority=2, category="UI", name="Pending feature",
                description="Original", steps=["a"], passes=False, in_progress=True,
            ))
            session.commit()
        self.SessionLocal = SessionLocal
        self._patch = patch.object(features_router, "_get_project_path", return_value=self.project_dir)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        engine, _ = create_database(self.project_dir)
        engine.dispose()
        self._tmp.cleanup()

    def _update(self, feature_id: int, update: FeatureUpdate):
        return asyncio.run(features_router.update_feature("proj", feature_id, update))

    def _get(self, feature_id: int) -> Feature:
        with self.SessionLocal() as session:
            return session.query(Feature).filter(Feature.id == feature_id).one()

    def test_edit_completed_feature_keeps_passing(self):
        resp = self._update(1, FeatureUpdate(description="Tweaked", steps=["a", "b"]))
        assert resp.description == "Tweaked"
        assert resp.steps == ["a", "b"]
        assert resp.passes is True
        assert self._get(1).passes is True

    def test_reopen_completed_feature(self):
        resp = self._update(1, FeatureUpdate(name="Renamed", reopen=True))
        assert resp.name == "Renamed"
        assert resp.passes is False
        assert resp.in_progress is False
        feature = self._get(1)
        assert feature.passes is False
        assert feature.in_progress is False

    def test_edit_pending_feature_does_not_touch_status(self):
        resp = self._update(2, FeatureUpdate(description="Clarified"))
        assert resp.description == "Clarified"
        assert resp.passes is False
        assert resp.in_progress is True


if __name__ == "__main__":
    unittest.main()
