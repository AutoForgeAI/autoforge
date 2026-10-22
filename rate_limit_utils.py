"""
Rate Limit Utilities
====================

Shared utilities for detecting and handling API rate limits.
Used by both agent.py (production) and test_rate_limit_utils.py (tests).
"""

import random
import re
from datetime import datetime, timedelta, timezone, tzinfo
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
]

# Compiled regex for efficient matching
_RATE_LIMIT_REGEX = re.compile(
    "|".join(RATE_LIMIT_REGEX_PATTERNS),
    re.IGNORECASE
)

# Regex patterns for Claude subscription usage limits (Pro/Max plan caps). The CLI
# reports these as a standalone line rather than an API error, e.g.:
#   "Limit reached · resets 6pm (America/New_York) · /upgrade to Max or turn on /extra-usage"
#   "5-hour limit reached ∙ resets 3am"
#   "Claude AI usage limit reached|1751234567"
#   "You've hit your limit · resets 9pm (Europe/London)"
# They are kept narrow (qualified limit name, a reset marker, or start of line) so
# prose like "File size limit reached" in agent output doesn't trigger a pause.
USAGE_LIMIT_REGEX_PATTERNS = [
    r"\b(?:usage|session|weekly|daily|opus|sonnet|\d+[-\s]?hour)\s+limit\s+(?:reached|exceeded)\b",
    r"\blimit\s+reached\s*[·∙•|]\s*(?:resets?\b|\d{9,})",
    r"^\s*you(?:'ve|’ve|\s+have)\s+(?:hit|reached)\s+your\s+(?:\w+\s+)?limit\b",
]

_USAGE_LIMIT_REGEX = re.compile(
    "|".join(USAGE_LIMIT_REGEX_PATTERNS),
    re.IGNORECASE | re.MULTILINE
)

# "resets 6pm", "resets at 6:30 pm (America/New_York)", "resets Oct 9, 10am (Europe/Paris)"
_RESET_TIME_REGEX = re.compile(
    r"\bresets?(?:\s+at)?\s+"
    r"(?:(?P<month>[a-z]{3,9})\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?,?\s+(?:at\s+)?)?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>am|pm)\b"
    r"(?:\s*\((?P<tz>[^)]+)\))?",
    re.IGNORECASE
)

# "usage limit reached|1751234567" (older CLI versions report a Unix timestamp)
_RESET_EPOCH_REGEX = re.compile(r"\blimit\s+reached\s*\|\s*(?P<epoch>\d{9,})", re.IGNORECASE)

_MONTHS = {
    name: index
    for index, names in enumerate(
        [
            ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"),
            ("may",), ("jun", "june"), ("jul", "july"), ("aug", "august"),
            ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"), ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}

# Usage limits reset within a week at most; anything further out is a parse error.
MAX_USAGE_LIMIT_WAIT = timedelta(days=8)

# Extra wait after the reported reset time before sending requests again
USAGE_LIMIT_RESUME_BUFFER_SECONDS = 60


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
    return bool(_RATE_LIMIT_REGEX.search(error_message)) or is_usage_limit_message(error_message)


def is_usage_limit_message(text: str) -> bool:
    """
    Detect a Claude subscription usage-limit message (e.g. the 5-hour or weekly cap).

    Unlike transient rate limits, these won't clear until the reported reset
    time, so callers should stop starting new sessions until then.

    Args:
        text: CLI output, response text, or an error message

    Returns:
        True if the text contains a usage-limit message, False otherwise.
    """
    return bool(_USAGE_LIMIT_REGEX.search(text))


def parse_reset_time(text: str, now: Optional[datetime] = None) -> Optional[datetime]:
    """
    Extract the time a usage limit resets from a CLI limit message.

    Handles:
    - "resets 6pm (America/New_York)" / "resets at 6:30pm" (next occurrence of that time)
    - "resets Oct 9, 10am (Europe/Paris)" (explicit date, used by weekly limits)
    - "usage limit reached|1751234567" (Unix timestamp)

    A missing or unknown timezone falls back to the local timezone.

    Args:
        text: The message to parse
        now: Current time (timezone-aware); defaults to the current local time

    Returns:
        A timezone-aware datetime in the future, or None if no reset time was found.
    """
    if now is None:
        now = datetime.now().astimezone()

    epoch_match = _RESET_EPOCH_REGEX.search(text)
    if epoch_match:
        try:
            target = datetime.fromtimestamp(int(epoch_match.group("epoch")), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
        return target if now < target <= now + MAX_USAGE_LIMIT_WAIT else None

    match = _RESET_TIME_REGEX.search(text)
    if not match:
        return None

    hour = int(match.group("hour"))
    minute = int(match.group("minute") or 0)
    if not 1 <= hour <= 12 or minute > 59:
        return None
    period = match.group("period").lower()
    if period == "pm" and hour != 12:
        hour += 12
    elif period == "am" and hour == 12:
        hour = 0

    tz: tzinfo = now.tzinfo or timezone.utc
    tz_name = match.group("tz")
    if tz_name:
        try:
            tz = ZoneInfo(tz_name.strip())
        except (ZoneInfoNotFoundError, ValueError):
            pass
    local_now = now.astimezone(tz)

    if match.group("month"):
        month = _MONTHS.get(match.group("month").lower())
        if month is None:
            return None
        try:
            target = local_now.replace(
                month=month, day=int(match.group("day")), hour=hour, minute=minute, second=0, microsecond=0
            )
        except ValueError:
            return None
        if target <= local_now:
            # Dates near New Year roll into the next year
            try:
                target = target.replace(year=target.year + 1)
            except ValueError:
                return None
    else:
        target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= local_now:
            target += timedelta(days=1)

    return target if target - local_now <= MAX_USAGE_LIMIT_WAIT else None


def format_reset_time(target: datetime) -> str:
    """Format a reset time for log output, e.g. "6:00 PM EDT (Oct 22)"."""
    return target.strftime("%I:%M %p %Z (%b %d)").lstrip("0")


def usage_limit_delay_seconds(reset_at: datetime, now: Optional[datetime] = None) -> int:
    """
    Seconds to wait before retrying after a usage limit, including a small buffer
    so the first request after the pause doesn't race the reset.

    Args:
        reset_at: Timezone-aware reset time (from parse_reset_time)
        now: Current time (timezone-aware); defaults to now

    Returns:
        Delay in seconds (at least 1)
    """
    if now is None:
        now = datetime.now(timezone.utc)
    remaining = (reset_at - now).total_seconds()
    return max(int(remaining) + USAGE_LIMIT_RESUME_BUFFER_SECONDS, 1)


def format_usage_limit_banner(reset_str: str, delay_seconds: int) -> str:
    """Build the warning shown when a Claude usage limit pauses the agent."""
    hours, remainder = divmod(int(delay_seconds), 3600)
    minutes = remainder // 60
    wait_str = f"{hours}h {minutes}m" if hours else f"{max(minutes, 1)}m"
    return "\n".join([
        "",
        "!" * 70,
        "  CLAUDE USAGE LIMIT REACHED",
        f"  Pausing until {reset_str} (~{wait_str}) instead of retrying.",
        "  Stop the agent to cancel; it will resume automatically after the reset.",
        "!" * 70,
    ])


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
