"""
Rate Limit Utilities
====================

Shared utilities for detecting and handling API rate limits.
Used by both agent.py (production) and test_rate_limit_utils.py (tests).
"""

import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

# Regex patterns for rate limit detection (used in both exception messages and response text)
# These patterns use word boundaries to avoid false positives like "PR #429" or "please wait while I..."
RATE_LIMIT_REGEX_PATTERNS = [
    r"\brate[_\s]?limit",         # "rate limit", "rate_limit", "ratelimit"
    r"\btoo\s+many\s+requests",   # "too many requests"
    r"\bhttp\s*429\b",            # "http 429", "http429"
    r"\bstatus\s*429\b",          # "status 429", "status429"
    r"\berror\s*429\b",           # "error 429", "error429"
    r"\b429\s+too\s+many",        # "429 too many"
    r"\b(?:server|api|system)\s+(?:is\s+)?overloaded\b",  # "server is overloaded", "api overloaded"
    r"\bquota\s*exceeded\b",      # "quota exceeded"
    # Claude subscription usage limits (5-hour / weekly), as printed by Claude Code, e.g.
    # "Limit reached · resets 6pm (America/New_York) · /upgrade to Max or turn on /extra-usage"
    # "5-hour limit reached ∙ resets 1pm", "You've hit your limit · resets 3am (Europe/London)"
    # "Claude AI usage limit reached|1760000000"
    # A bare "limit reached" is deliberately NOT matched ("File size limit reached").
    r"\blimit\s+reached\W{0,5}resets?\b",
    r"\b(?:you've|you\s+have)\s+hit\s+your\s+(?:[\w-]+\s+)?limit\b",
    r"\bclaude(?:\s+ai)?\s+usage\s+limit\s+reached\b",
]

# Compiled regex for efficient matching
_RATE_LIMIT_REGEX = re.compile(
    "|".join(RATE_LIMIT_REGEX_PATTERNS),
    re.IGNORECASE
)


def parse_retry_after(error_message: str) -> Optional[int]:
    """
    Extract retry-after seconds from various error message formats.

    Handles common formats:
    - "Retry-After: 60"
    - "retry after 60 seconds"
    - "try again in 5 seconds"
    - "30 seconds remaining"

    Args:
        error_message: The error message to parse

    Returns:
        Seconds to wait, or None if not parseable.
    """
    # Patterns require explicit "seconds" or "s" unit, OR no unit at all (end of string/sentence)
    # This prevents matching "30 minutes" or "1 hour" since those have non-seconds units
    patterns = [
        r"retry.?after[:\s]+(\d+)\s*(?:seconds?|s\b)",  # Requires seconds unit
        r"retry.?after[:\s]+(\d+)(?:\s*$|\s*[,.])",     # Or end of string/sentence
        r"try again in\s+(\d+)\s*(?:seconds?|s\b)",     # Requires seconds unit
        r"try again in\s+(\d+)(?:\s*$|\s*[,.])",        # Or end of string/sentence
        r"(\d+)\s*seconds?\s*(?:remaining|left|until)",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


# Longest wait we will honor from a parsed usage-limit reset time.
# Weekly limits can legitimately be several days away.
MAX_LIMIT_RESET_SECONDS = 7 * 24 * 60 * 60

# "resets 6pm (America/New_York)", "resets at 6:30 PM (UTC)", "will reset at 3pm"
_RESET_TIME_REGEX = re.compile(
    r"\breset(?:s)?(?:\s+at)?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b(?:\s*\(([^)]+)\))?",
    re.IGNORECASE,
)

# Legacy Claude Code format: "Claude AI usage limit reached|1760000000" (unix epoch seconds)
_RESET_EPOCH_REGEX = re.compile(r"usage\s+limit\s+reached\|(\d{10})\b", re.IGNORECASE)


def parse_limit_reset(text: str, now: Optional[datetime] = None) -> Optional[tuple[int, datetime]]:
    """
    Extract when a Claude usage limit resets from a limit message.

    Handles:
    - "Limit reached · resets 6pm (America/New_York)"  (time of day, optional IANA timezone)
    - "Claude AI usage limit reached|1760000000"       (unix epoch)

    A time of day without a timezone is interpreted in the local timezone. A time
    that has already passed today is taken to mean tomorrow.

    Args:
        text: The message to parse
        now: Current time (timezone-aware); defaults to the real current time. For tests.

    Returns:
        (seconds_until_reset, reset_datetime) or None if no reset time was found.
        Seconds are clamped to 1..MAX_LIMIT_RESET_SECONDS.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    target: Optional[datetime] = None

    epoch_match = _RESET_EPOCH_REGEX.search(text)
    if epoch_match:
        target = datetime.fromtimestamp(int(epoch_match.group(1)), tz=timezone.utc)
    else:
        match = _RESET_TIME_REGEX.search(text)
        if not match:
            return None

        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        if not (1 <= hour <= 12 and 0 <= minute <= 59):
            return None
        period = match.group(3).lower()
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        tz_name = match.group(4).strip() if match.group(4) else None
        try:
            local_now = now.astimezone(ZoneInfo(tz_name)) if tz_name else now.astimezone()
        except Exception:
            # Unknown timezone name - fall back to local time rather than giving up
            local_now = now.astimezone()

        target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= local_now:
            target += timedelta(days=1)

    seconds = int((target - now).total_seconds())
    seconds = min(max(seconds, 1), MAX_LIMIT_RESET_SECONDS)
    return seconds, target


# Machine-readable line printed by single-session agents (orchestrator mode) when they
# stop because of a rate/usage limit, so the orchestrator can pause instead of respawning.
RATE_LIMIT_MARKER = "[RATE_LIMIT]"
_RATE_LIMIT_MARKER_REGEX = re.compile(r"\[RATE_LIMIT\]\s+retry_in=(\d+|unknown)\b")


def format_rate_limit_marker(retry_seconds: Optional[int], detail: str = "") -> str:
    """Build the marker line an agent prints when it stops on a rate limit."""
    retry = str(retry_seconds) if retry_seconds is not None else "unknown"
    line = f"{RATE_LIMIT_MARKER} retry_in={retry}"
    if detail:
        line += f" {detail}"
    return line


def parse_rate_limit_marker(line: str) -> tuple[bool, Optional[int]]:
    """
    Parse a marker line produced by format_rate_limit_marker().

    Returns:
        (is_marker, retry_seconds). retry_seconds is None when the line is not a
        marker or when the agent did not know how long to wait.
    """
    match = _RATE_LIMIT_MARKER_REGEX.search(line)
    if not match:
        return False, None
    value = match.group(1)
    return True, (None if value == "unknown" else int(value))


def is_rate_limit_error(error_message: str) -> bool:
    """
    Detect if an error message indicates a rate limit.

    Uses regex patterns with word boundaries to avoid false positives
    like "PR #429", "please wait while I...", or "Node v14.29.0".

    Args:
        error_message: The error message to check

    Returns:
        True if the message indicates a rate limit, False otherwise.
    """
    return bool(_RATE_LIMIT_REGEX.search(error_message))


def calculate_rate_limit_backoff(retries: int) -> int:
    """
    Calculate exponential backoff with jitter for rate limits.

    Base formula: min(15 * 2^retries, 3600)
    Jitter: adds 0-30% random jitter to prevent thundering herd.
    Base sequence: ~15-20s, ~30-40s, ~60-78s, ~120-156s, ...

    The lower starting delay (15s vs 60s) allows faster recovery from
    transient rate limits, while jitter prevents synchronized retries
    when multiple agents hit limits simultaneously.

    Args:
        retries: Number of consecutive rate limit retries (0-indexed)

    Returns:
        Delay in seconds (clamped to 1-3600 range, with jitter)
    """
    base = int(min(max(15 * (2 ** retries), 1), 3600))
    jitter = random.uniform(0, base * 0.3)
    return int(base + jitter)


def calculate_error_backoff(retries: int) -> int:
    """
    Calculate linear backoff for non-rate-limit errors.

    Formula: min(30 * retries, 300) - caps at 5 minutes
    Sequence: 30s, 60s, 90s, 120s, ... 300s

    Args:
        retries: Number of consecutive error retries (1-indexed)

    Returns:
        Delay in seconds (clamped to 1-300 range)
    """
    return min(max(30 * retries, 1), 300)


def clamp_retry_delay(delay_seconds: int) -> int:
    """
    Clamp a retry delay to a safe range (1-3600 seconds).

    Args:
        delay_seconds: The raw delay value

    Returns:
        Delay clamped to 1-3600 seconds
    """
    return min(max(delay_seconds, 1), 3600)
