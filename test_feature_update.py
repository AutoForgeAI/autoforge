"""
Unit tests for editing features via PATCH /api/projects/{name}/features/{id}.

Calls the route handler directly against a temporary project database.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from server.routers import features as features_router
from server.schemas import FeatureUpdate


class TestUpdateFeature(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)
        _, Feature = features_router._get_db_classes()
        with features_router.get_db_session(self.project_dir) as session:
            session.add(Feature(
                id=1, priority=1, category="UI", name="Done feature",
                description="Original", steps=["step"], passes=True, in_progress=False,
            ))
            session.add(Feature(
                id=2, priority=2, category="UI", name="Pending feature",
                description="Original", steps=["step"], passes=False, in_progress=False,
            ))
            session.commit()
        self._patch = patch.object(features_router, "_get_project_path", return_value=self.project_dir)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _update(self, feature_id: int, update: FeatureUpdate):
        return asyncio.run(features_router.update_feature("demo", feature_id, update))

    def test_edit_completed_feature_keeps_it_done(self):
        result = self._update(1, FeatureUpdate(description="Tweaked"))
        assert result.description == "Tweaked"
        assert result.passes is True

    def test_edit_completed_feature_with_reopen(self):
        result = self._update(1, FeatureUpdate(name="Renamed", reopen=True))
        assert result.name == "Renamed"
        assert result.passes is False
        assert result.in_progress is False

    def test_reopen_on_pending_feature_is_noop(self):
        result = self._update(2, FeatureUpdate(description="Tweaked", reopen=True))
        assert result.description == "Tweaked"
        assert result.passes is False

    def test_missing_feature_returns_404(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as ctx:
            self._update(99, FeatureUpdate(name="x"))
        assert ctx.exception.status_code == 404


if __name__ == "__main__":
    unittest.main()
