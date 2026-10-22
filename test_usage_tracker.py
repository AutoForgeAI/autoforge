"""
Tests for token/cost usage tracking and cost limits (usage_tracker.py).

Run with: python -m pytest test_usage_tracker.py
"""

from dataclasses import dataclass
from pathlib import Path

import pytest

import registry
import usage_tracker
from api.database import dispose_engine


@dataclass
class FakeResultMessage:
    total_cost_usd: float | None = 0.0
    usage: dict | None = None
    duration_ms: int = 0
    num_turns: int = 0


@pytest.fixture
def project_dir(tmp_path: Path):
    yield tmp_path
    dispose_engine(tmp_path)


@pytest.fixture
def cost_limit(monkeypatch):
    """Set the max_cost_usd setting without touching the real registry."""
    settings: dict[str, str] = {}

    def fake_get_setting(key, default=None):
        return settings.get(key, default)

    monkeypatch.setattr(registry, "get_setting", fake_get_setting)

    def set_limit(value: str | None):
        if value is None:
            settings.pop(usage_tracker.COST_LIMIT_SETTING, None)
        else:
            settings[usage_tracker.COST_LIMIT_SETTING] = value

    return set_limit


def test_extract_usage_full():
    msg = FakeResultMessage(
        total_cost_usd=0.1234,
        usage={
            "input_tokens": 100,
            "output_tokens": 50,
            "cache_creation_input_tokens": 10,
            "cache_read_input_tokens": 2000,
        },
        duration_ms=4200,
        num_turns=7,
    )
    assert usage_tracker.extract_usage(msg) == {
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_creation_tokens": 10,
        "cache_read_tokens": 2000,
        "cost_usd": 0.1234,
        "duration_ms": 4200,
        "num_turns": 7,
    }


def test_extract_usage_tolerates_missing_and_bad_values():
    msg = FakeResultMessage(total_cost_usd=None, usage={"input_tokens": "oops"})
    usage = usage_tracker.extract_usage(msg)
    assert usage["input_tokens"] == 0
    assert usage["output_tokens"] == 0
    assert usage["cost_usd"] == 0.0

    assert usage_tracker.extract_usage(object())["cost_usd"] == 0.0


def test_totals_empty_without_database(project_dir):
    totals = usage_tracker.get_usage_totals(project_dir)
    assert totals["sessions"] == 0
    assert totals["cost_usd"] == 0.0
    assert usage_tracker.get_recent_sessions(project_dir) == []


def test_record_and_sum_usage(project_dir):
    usage_tracker.record_usage(
        project_dir,
        {"input_tokens": 10, "output_tokens": 5, "cost_usd": 0.5},
        agent_type="coding",
        feature_ids=[1, 2],
        model="claude-opus-4-7",
    )
    usage_tracker.record_usage(
        project_dir,
        {"input_tokens": 1, "output_tokens": 2, "cache_read_tokens": 3, "cost_usd": 0.25},
        agent_type="testing",
    )

    totals = usage_tracker.get_usage_totals(project_dir)
    assert totals["sessions"] == 2
    assert totals["input_tokens"] == 11
    assert totals["output_tokens"] == 7
    assert totals["cache_read_tokens"] == 3
    assert totals["cost_usd"] == pytest.approx(0.75)

    recent = usage_tracker.get_recent_sessions(project_dir)
    assert [r["agent_type"] for r in recent] == ["testing", "coding"]
    assert recent[1]["feature_ids"] == [1, 2]
    assert recent[1]["model"] == "claude-opus-4-7"


def test_reset_usage(project_dir):
    usage_tracker.record_usage(project_dir, {"cost_usd": 1.0})
    assert usage_tracker.reset_usage(project_dir) == 1
    assert usage_tracker.get_usage_totals(project_dir)["cost_usd"] == 0.0


@pytest.mark.parametrize("raw", [None, "", "0", "-5", "abc"])
def test_no_limit_when_unset_or_invalid(project_dir, cost_limit, raw):
    cost_limit(raw)
    usage_tracker.record_usage(project_dir, {"cost_usd": 100.0})
    assert usage_tracker.get_cost_limit() is None
    assert usage_tracker.check_cost_limit(project_dir) == (False, 0.0, None)


def test_limit_enforced(project_dir, cost_limit):
    cost_limit("1.5")
    usage_tracker.record_usage(project_dir, {"cost_usd": 1.0})
    reached, total, limit = usage_tracker.check_cost_limit(project_dir)
    assert (reached, limit) == (False, 1.5)
    assert total == pytest.approx(1.0)

    usage_tracker.record_usage(project_dir, {"cost_usd": 0.5})
    reached, total, limit = usage_tracker.check_cost_limit(project_dir)
    assert reached is True
    assert total == pytest.approx(1.5)

    msg = usage_tracker.format_cost_limit_message(total, limit)
    assert "$1.50" in msg
