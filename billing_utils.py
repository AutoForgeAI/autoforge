"""
Billing Utilities
=================

Spend safeguards for autonomous agent runs (see GitHub issue #162):

- Detect "out of credits" / billing errors so agents stop instead of
  retrying in a loop.
- Optional spending cap via the ``AUTOFORGE_MAX_BUDGET_USD`` environment
  variable, enforced per agent process and across all agents by the
  parallel orchestrator.
- A machine-readable per-session cost line that agents print and the
  orchestrator parses to aggregate spend.

Note: Anthropic Console spend limits and credit balances are enforced by
Anthropic with some delay, so a fast autonomous run can overshoot them.
These local checks stop AutoForge itself from continuing to spend.
"""

import os
import re
from typing import Optional

# Exit code an agent process uses when it stopped because of a billing error
# (credit balance exhausted). The orchestrator treats it as fatal for the run.
BILLING_ERROR_EXIT_CODE = 3

# Exit code an agent process uses when it stopped because the configured
# spending cap was reached.
BUDGET_EXCEEDED_EXIT_CODE = 4

# Environment variable holding the optional spending cap in USD.
MAX_BUDGET_ENV_VAR = "AUTOFORGE_MAX_BUDGET_USD"

# Regex patterns for billing / credit exhaustion errors. These are only
# matched against error contexts (exceptions, API error messages, failed
# results), never against the agent's normal output.
BILLING_ERROR_REGEX_PATTERNS = [
    r"\bcredit\s+balance\s+is\s+too\s+low",         # Anthropic API / Claude CLI
    r"\bout\s+of\s+(?:usage\s+)?credits\b",          # "out of usage credits"
    r"\binsufficient[_\s]+(?:credits?|funds|balance|quota)\b",  # GLM, Kimi, generic
    r"\bbilling[_\s]error\b",                       # "billing_error" error type
    r"\bpayment\s+required\b",                      # HTTP 402
]

_BILLING_ERROR_REGEX = re.compile("|".join(BILLING_ERROR_REGEX_PATTERNS), re.IGNORECASE)

# Line printed by agents after each session so the orchestrator can
# aggregate spend across parallel agent processes.
SESSION_COST_PREFIX = "[AUTOFORGE_SESSION_COST]"
_SESSION_COST_REGEX = re.compile(re.escape(SESSION_COST_PREFIX) + r"\s+usd=(\d+(?:\.\d+)?)")

BILLING_ERROR_HELP = """
======================================================================
  BILLING ERROR - AGENT STOPPED
======================================================================
The API reported that your credit balance is exhausted, so AutoForge
stopped instead of retrying (retries can keep consuming credits while
Anthropic's billing catches up).

What to check:
  - If ANTHROPIC_API_KEY (or ANTHROPIC_AUTH_TOKEN) is set in your
    environment or .env, the Claude CLI bills that Anthropic API account
    per token - even if you are also logged in with a Claude subscription.
  - Anthropic Console spend limits and credit balances are enforced with
    a delay, so a fast run can overshoot them. Set
    AUTOFORGE_MAX_BUDGET_USD to have AutoForge stop itself at a cap.
  - Add credits in the Anthropic Console, then start the agent again.
======================================================================
"""


def is_billing_error(error_message: str) -> bool:
    """
    Detect if an error message indicates exhausted credits / a billing problem.

    Args:
        error_message: The error message to check

    Returns:
        True if the message indicates a billing error, False otherwise.
    """
    return bool(_BILLING_ERROR_REGEX.search(error_message))


def parse_budget(value: Optional[str]) -> Optional[float]:
    """
    Parse a spending cap value.

    Args:
        value: Raw value (e.g. "20", "12.50", "$5")

    Returns:
        The cap in USD, or None when unset, empty, invalid or not positive.
    """
    if value is None:
        return None
    value = value.strip().lstrip("$").strip()
    if not value:
        return None
    try:
        budget = float(value)
    except ValueError:
        return None
    if budget != budget or budget <= 0 or budget == float("inf"):  # NaN, non-positive, inf
        return None
    return budget


def get_max_budget_usd() -> Optional[float]:
    """Return the spending cap from AUTOFORGE_MAX_BUDGET_USD, or None if not set/invalid."""
    return parse_budget(os.environ.get(MAX_BUDGET_ENV_VAR))


def format_session_cost_line(cost_usd: float) -> str:
    """Format the machine-readable per-session cost line printed by agents."""
    return f"{SESSION_COST_PREFIX} usd={cost_usd:.6f}"


def parse_session_cost_line(line: str) -> Optional[float]:
    """
    Extract the session cost from an agent output line.

    Args:
        line: A line of agent output (may carry a prefix such as "[Feature #3] ")

    Returns:
        The session cost in USD, or None if the line is not a cost line.
    """
    match = _SESSION_COST_REGEX.search(line)
    if not match:
        return None
    return float(match.group(1))


def uses_api_key_billing() -> bool:
    """
    True when an Anthropic API key / auth token is configured for direct
    Anthropic API access (pay-per-token billing rather than a Claude
    subscription). Alternative providers (custom base URL) and Vertex AI are
    excluded since they bill elsewhere.
    """
    if os.environ.get("CLAUDE_CODE_USE_VERTEX") == "1" or os.environ.get("ANTHROPIC_BASE_URL"):
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
