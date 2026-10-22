"""
Unit tests for spend safeguards (issue #162).

Covers billing error detection and budget parsing in billing_utils.py, billing
detection / cost tracking in agent.py, and cost aggregation / halting in
parallel_orchestrator.py.
"""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

import agent
from billing_utils import (
    BILLING_ERROR_EXIT_CODE,
    BUDGET_EXCEEDED_EXIT_CODE,
    MAX_BUDGET_ENV_VAR,
    format_session_cost_line,
    get_max_budget_usd,
    is_billing_error,
    parse_budget,
    parse_session_cost_line,
    uses_api_key_billing,
)


class TestIsBillingError(unittest.TestCase):
    def test_anthropic_credit_messages(self):
        assert is_billing_error("Credit balance is too low")
        assert is_billing_error(
            "Your credit balance is too low to access the Anthropic API. "
            "Please go to Plans & Billing to upgrade or purchase credits."
        )
        assert is_billing_error("your organization is out of usage credits")
        assert is_billing_error("billing_error")

    def test_provider_messages(self):
        assert is_billing_error("Insufficient balance or no resource package")
        assert is_billing_error("insufficient_quota")
        assert is_billing_error("HTTP 402 Payment Required")

    def test_non_billing_errors(self):
        assert not is_billing_error("rate limit exceeded")
        assert not is_billing_error("Connection reset by peer")
        assert not is_billing_error("Invalid API key")
        assert not is_billing_error("Added credits page to the billing dashboard")
        assert not is_billing_error("")


class TestParseBudget(unittest.TestCase):
    def test_valid(self):
        assert parse_budget("20") == 20.0
        assert parse_budget(" 12.50 ") == 12.5
        assert parse_budget("$5") == 5.0

    def test_invalid(self):
        for value in [None, "", "  ", "abc", "0", "-3", "nan", "inf"]:
            assert parse_budget(value) is None, value

    def test_env(self):
        with mock.patch.dict(os.environ, {MAX_BUDGET_ENV_VAR: "7.5"}):
            assert get_max_budget_usd() == 7.5
        with mock.patch.dict(os.environ, {}, clear=True):
            assert get_max_budget_usd() is None


class TestSessionCostLine(unittest.TestCase):
    def test_round_trip(self):
        line = format_session_cost_line(0.123456)
        assert parse_session_cost_line(line) == 0.123456
        assert parse_session_cost_line(f"[Feature #3] {line}") == 0.123456

    def test_non_cost_lines(self):
        assert parse_session_cost_line("Session cost (estimated): $0.12") is None
        assert parse_session_cost_line("[Tool: Bash]") is None


class TestUsesApiKeyBilling(unittest.TestCase):
    def test_detection(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}, clear=True):
            assert uses_api_key_billing()
        with mock.patch.dict(os.environ, {}, clear=True):
            assert not uses_api_key_billing()
        with mock.patch.dict(
            os.environ, {"ANTHROPIC_AUTH_TOKEN": "t", "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic"}, clear=True
        ):
            assert not uses_api_key_billing()
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k", "CLAUDE_CODE_USE_VERTEX": "1"}, clear=True):
            assert not uses_api_key_billing()


def _result(cost, is_error=False, result=None):
    return ResultMessage(
        subtype="success", duration_ms=1, duration_api_ms=1, is_error=is_error,
        num_turns=1, session_id="s", total_cost_usd=cost, result=result,
    )


class FakeClient:
    """Minimal stand-in for ClaudeSDKClient that replays scripted messages."""

    def __init__(self, messages=None, query_error=None):
        self.messages = messages or []
        self.query_error = query_error
        self.queries = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def query(self, message):
        self.queries += 1
        if self.query_error:
            raise self.query_error

    async def receive_response(self):
        for msg in self.messages:
            yield msg


class TestRunAgentSession(unittest.TestCase):
    def run_session(self, client):
        costs: list[float] = []
        status, text = asyncio.run(agent.run_agent_session(client, "prompt", Path("."), costs))
        return status, text, costs

    def test_normal_session_reports_cost(self):
        client = FakeClient([
            AssistantMessage(content=[TextBlock(text="Implemented the feature.")], model="claude-sonnet"),
            _result(0.42),
        ])
        status, _, costs = self.run_session(client)
        assert status == "continue"
        assert costs == [0.42]

    def test_billing_error_assistant_message(self):
        client = FakeClient([
            AssistantMessage(
                content=[TextBlock(text="Credit balance is too low")], model="<synthetic>", error="billing_error"
            ),
            _result(0.0, is_error=True, result="Credit balance is too low"),
        ])
        status, text, _ = self.run_session(client)
        assert status == "billing"
        assert "Credit balance" in text

    def test_billing_error_old_sdk_synthetic_message(self):
        client = FakeClient([
            AssistantMessage(content=[TextBlock(text="Credit balance is too low")], model="<synthetic>"),
        ])
        status, _, _ = self.run_session(client)
        assert status == "billing"

    def test_agent_text_mentioning_balance_is_not_billing_error(self):
        # A normal assistant message (e.g. while building a banking app) must not stop the run
        client = FakeClient([
            AssistantMessage(
                content=[TextBlock(text="Show 'Insufficient balance' when credit balance is too low")],
                model="claude-sonnet",
            ),
            _result(0.1),
        ])
        status, _, _ = self.run_session(client)
        assert status == "continue"

    def test_billing_error_exception(self):
        client = FakeClient(query_error=RuntimeError("API error 400: Your credit balance is too low"))
        status, _, _ = self.run_session(client)
        assert status == "billing"


class TestRunAutonomousAgent(unittest.TestCase):
    def run_agent(self, client_factory, env=None, **kwargs):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.dict(os.environ, env or {}, clear=True), \
                mock.patch.object(agent, "create_client", side_effect=client_factory), \
                mock.patch.object(agent, "get_coding_prompt", return_value="prompt"), \
                mock.patch.object(agent, "print_progress_summary"), \
                mock.patch.object(agent, "print_session_header"), \
                mock.patch.object(agent, "count_passing_tests", return_value=(0, 0, 5, 0)), \
                mock.patch.object(agent.asyncio, "sleep", new=mock.AsyncMock()):
            return asyncio.run(agent.run_autonomous_agent(Path(tmp), "model", agent_type="coding", **kwargs))

    def test_billing_error_stops_without_retry(self):
        clients = []

        def factory(*args, **kwargs):
            client = FakeClient([
                AssistantMessage(
                    content=[TextBlock(text="Credit balance is too low")], model="<synthetic>", error="billing_error"
                ),
            ])
            clients.append(client)
            return client

        code = self.run_agent(factory, max_iterations=10)
        assert code == BILLING_ERROR_EXIT_CODE
        assert len(clients) == 1  # no retry loop

    def test_budget_cap_stops_loop(self):
        clients = []

        def factory(*args, **kwargs):
            client = FakeClient([
                AssistantMessage(content=[TextBlock(text="Working...")], model="claude-sonnet"),
                _result(0.6),
            ])
            clients.append(client)
            return client

        code = self.run_agent(factory, env={MAX_BUDGET_ENV_VAR: "1"}, max_iterations=10)
        assert code == BUDGET_EXCEEDED_EXIT_CODE
        assert len(clients) == 2  # $0.60 then $1.20 >= $1.00

    def test_no_budget_runs_to_max_iterations(self):
        def factory(*args, **kwargs):
            return FakeClient([_result(5.0)])

        assert self.run_agent(factory, max_iterations=3) == 0


class TestOrchestratorSpendGuard(unittest.TestCase):
    def make_orchestrator(self, tmp, env=None):
        from parallel_orchestrator import ParallelOrchestrator

        with mock.patch.dict(os.environ, env or {}, clear=True):
            orch = ParallelOrchestrator(project_dir=Path(tmp))
        self.addCleanup(orch.cleanup)
        return orch

    def test_aggregates_cost_and_halts_at_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orchestrator(tmp, {MAX_BUDGET_ENV_VAR: "1.00"})
            orch._record_cost_from_line(f"[Feature #1] {format_session_cost_line(0.4)}")
            orch._record_cost_from_line(format_session_cost_line(0.4))
            assert orch._spend_stop_reason is None
            orch._record_cost_from_line(format_session_cost_line(0.3))
            assert abs(orch.total_cost_usd - 1.1) < 1e-9
            assert orch._spend_stop_reason == "budget"
            assert orch.start_feature(1) == (False, "Run halted for spend safeguard")
            assert orch.start_feature_batch([1, 2]) == (False, "Run halted for spend safeguard")
            assert orch._spawn_testing_agent() == (False, "Run halted for spend safeguard")

    def test_no_cap_never_halts(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orchestrator(tmp)
            orch._record_cost_from_line(format_session_cost_line(1000))
            assert orch._spend_stop_reason is None

    def test_agent_billing_exit_halts_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = self.make_orchestrator(tmp)
            proc = mock.Mock(pid=1234)
            with mock.patch.object(orch, "_run_inter_session_cleanup"):
                orch._on_agent_complete(5, BILLING_ERROR_EXIT_CODE, "testing", proc)
            assert orch._spend_stop_reason == "billing"


if __name__ == "__main__":
    unittest.main()
