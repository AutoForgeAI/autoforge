"""
Rate Limit Utilities
====================

Shared utilities for detecting and handling API rate limits.
Used by both agent.py (production) and test_rate_limit_utils.py (tests).
"""

import random
import re
from typing import Optional

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
    r"\bclaude\s+usage\s+limit\s+reached",  # "claude usage limit reached"
    r"\byour\s+limit\s+will\s+reset\s+at", # "your limit will reset at"
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


def parse_claude_reset_time(error_message: str) -> Optional[tuple[int, str]]:
    """
    Extract Claude usage limit reset time and timezone from error message.

    Handles format: "Your limit will reset at 3pm (America/Santiago)"
    
    Args:
        error_message: The error message to parse
        
    Returns:
        Tuple of (seconds_until_reset, formatted_reset_time) or None if not parseable
    """
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    
    # Match patterns like "resets at 3pm (America/Santiago)" or "reset at 3:30pm (UTC)"
    match = re.search(
        r"(?i)\b(?:resets?|will\s+reset)\s+at\s+(\d+)(?::(\d+))?\s*(am|pm)\s*\(([^)]+)\)",
        error_message,
    )
    
    if match:
        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = match.group(3).lower()
        tz_name = match.group(4).strip()

        # Convert to 24-hour format
        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        try:
            tz = ZoneInfo(tz_name)
            now = datetime.now(tz)
            target = now.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )

            # If target time has already passed today, wait until tomorrow
            if target <= now:
                target += timedelta(days=1)

            delta = target - now
            seconds_until_reset = min(max(int(delta.total_seconds()), 1), 24 * 60 * 60)
            formatted_reset_time = target.strftime("%B %d, %Y at %I:%M %p %Z")
            
            return seconds_until_reset, formatted_reset_time

        except Exception:
            # Invalid timezone or other parsing error
            pass
    
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
