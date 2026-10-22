#!/usr/bin/env python3
"""
Feature Split Tests
===================

Tests for the feature_split MCP tool, which breaks a too-large feature into
smaller sub-features instead of letting the agent skip it or pass it untested.

Run with: python -m pytest test_feature_split.py -v
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import mcp_server.feature_mcp as feature_mcp
from api.database import Feature, create_database
from api.dependency_resolver import MAX_DEPENDENCIES_PER_FEATURE


def _sub(name: str, **extra) -> dict:
    return {"name": name, "description": f"{name} description", "steps": [f"verify {name}"], **extra}


class FeatureSplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.engine, self.session_maker = create_database(self.tmp)
        feature_mcp._engine = self.engine
        feature_mcp._session_maker = self.session_maker

        with self.session_maker() as session:
            base = Feature(priority=1, category="Core", name="Base", description="d", steps=["s"],
                           passes=True, in_progress=False)
            big = Feature(priority=5, category="Checkout", name="Big", description="d", steps=["s"],
                          passes=False, in_progress=True)
            session.add_all([base, big])
            session.flush()
            big.dependencies = [base.id]
            session.commit()
            self.base_id = base.id
            self.big_id = big.id

    def tearDown(self):
        self.engine.dispose()
        feature_mcp._engine = None
        feature_mcp._session_maker = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _get(self, feature_id: int):
        with self.session_maker() as session:
            feature = session.query(Feature).filter(Feature.id == feature_id).first()
            session.expunge(feature)
            return feature

    def test_split_creates_sub_features_and_blocks_parent(self):
        result = json.loads(feature_mcp.feature_split(
            self.big_id, [_sub("Cart"), _sub("Payment", category="Payments")]
        ))

        self.assertTrue(result["success"])
        sub_ids = result["sub_feature_ids"]
        self.assertEqual(len(sub_ids), 2)
        self.assertEqual(result["parent_dependencies"], sorted([self.base_id, *sub_ids]))

        parent = self._get(self.big_id)
        self.assertFalse(parent.in_progress)
        self.assertFalse(parent.passes)
        self.assertEqual(parent.dependencies, sorted([self.base_id, *sub_ids]))

        cart, payment = self._get(sub_ids[0]), self._get(sub_ids[1])
        self.assertEqual(cart.category, "Checkout")  # inherited
        self.assertEqual(payment.category, "Payments")
        for sub in (cart, payment):
            self.assertEqual(sub.priority, 5)
            self.assertEqual(sub.dependencies, [self.base_id])
            self.assertFalse(sub.passes)
            self.assertFalse(sub.in_progress)

    def test_parent_is_ready_only_after_sub_features_pass(self):
        result = json.loads(feature_mcp.feature_split(self.big_id, [_sub("A"), _sub("B")]))
        sub_ids = result["sub_feature_ids"]

        ready_ids = {f["id"] for f in json.loads(feature_mcp.feature_get_ready(50))["features"]}
        self.assertEqual(ready_ids, set(sub_ids))

        for fid in sub_ids:
            self.assertTrue(json.loads(feature_mcp.feature_mark_passing(fid))["success"])

        ready_ids = {f["id"] for f in json.loads(feature_mcp.feature_get_ready(50))["features"]}
        self.assertEqual(ready_ids, {self.big_id})

    def test_cannot_split_passing_feature(self):
        result = json.loads(feature_mcp.feature_split(self.base_id, [_sub("A"), _sub("B")]))
        self.assertIn("already passing", result["error"])

    def test_missing_feature(self):
        result = json.loads(feature_mcp.feature_split(9999, [_sub("A"), _sub("B")]))
        self.assertIn("not found", result["error"])

    def test_invalid_sub_feature_rejected_without_changes(self):
        cases = [
            [_sub("A"), {"name": "B", "description": "d"}],  # missing steps
            [_sub("A"), {"name": "", "description": "d", "steps": ["s"]}],  # empty name
            [_sub("A"), {"name": "B", "description": "d", "steps": []}],  # empty steps
            [_sub("A"), _sub("B", category="")],  # empty category
        ]
        for subs in cases:
            result = json.loads(feature_mcp.feature_split(self.big_id, subs))
            self.assertIn("error", result, subs)

        with self.session_maker() as session:
            self.assertEqual(session.query(Feature).count(), 2)
        self.assertEqual(self._get(self.big_id).dependencies, [self.base_id])

    def test_dependency_limit_enforced(self):
        with self.session_maker() as session:
            fillers = [Feature(priority=1, category="c", name=f"f{i}", description="d", steps=["s"],
                               passes=True, in_progress=False)
                       for i in range(MAX_DEPENDENCIES_PER_FEATURE - 2)]
            session.add_all(fillers)
            session.flush()
            big = session.query(Feature).filter(Feature.id == self.big_id).first()
            big.dependencies = [self.base_id] + [f.id for f in fillers]
            session.commit()

        result = json.loads(feature_mcp.feature_split(self.big_id, [_sub("A"), _sub("B")]))
        self.assertIn("dependencies", result["error"])


if __name__ == "__main__":
    unittest.main()
