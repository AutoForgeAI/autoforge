"""
Unit tests for rate limit handling functions.

Tests the parse_retry_after(), is_rate_limit_error(), and backoff calculation
functions from rate_limit_utils.py (shared module).
"""

import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from rate_limit_utils import (
    calculate_error_backoff,
    calculate_rate_limit_backoff,
    clamp_retry_delay,
    format_rate_limit_marker,
    is_rate_limit_error,
    parse_limit_reset,
    parse_rate_limit_marker,
    parse_retry_after,
)


class TestParseRetryAfter(unittest.TestCase):
    """Tests for parse_retry_after() function."""

    def test_retry_after_colon_format(self):
        """Test 'Retry-After: 60' format."""
        assert parse_retry_after("Retry-After: 60") == 60
        assert parse_retry_after("retry-after: 120") == 120
        assert parse_retry_after("retry after: 30 seconds") == 30

    def test_retry_after_space_format(self):
        """Test 'retry after 60 seconds' format."""
        assert parse_retry_after("retry after 60 seconds") == 60
        assert parse_retry_after("Please retry after 120 seconds") == 120
        assert parse_retry_after("Retry after 30") == 30

    def test_try_again_in_format(self):
        """Test 'try again in X seconds' format."""
        assert parse_retry_after("try again in 120 seconds") == 120
        assert parse_retry_after("Please try again in 60s") == 60
        assert parse_retry_after("Try again in 30 seconds") == 30

    def test_seconds_remaining_format(self):
        """Test 'X seconds remaining' format."""
        assert parse_retry_after("30 seconds remaining") == 30
        assert parse_retry_after("60 seconds left") == 60
        assert parse_retry_after("120 seconds until reset") == 120

    def test_retry_after_zero(self):
        """Test 'Retry-After: 0' returns 0 (not None)."""
        assert parse_retry_after("Retry-After: 0") == 0
        assert parse_retry_after("retry after 0 seconds") == 0

    def test_no_match(self):
        """Test messages that don't contain retry-after info."""
        assert parse_retry_after("no match here") is None
        assert parse_retry_after("Connection refused") is None
        assert parse_retry_after("Internal server error") is None
        assert parse_retry_after("") is None

    def test_minutes_not_supported(self):
        """Test that minutes are not parsed (by design)."""
        # We only support seconds to avoid complexity
        # These patterns should NOT match when followed by minute/hour units
        assert parse_retry_after("wait 5 minutes") is None
        assert parse_retry_after("try again in 2 minutes") is None
        assert parse_retry_after("retry after 5 minutes") is None
        assert parse_retry_after("retry after 1 hour") is None
        assert parse_retry_after("try again in 30 min") is None


class TestIsRateLimitError(unittest.TestCase):
    """Tests for is_rate_limit_error() function."""

    def test_rate_limit_patterns(self):
        """Test various rate limit error messages."""
        assert is_rate_limit_error("Rate limit exceeded") is True
        assert is_rate_limit_error("rate_limit_exceeded") is True
        assert is_rate_limit_error("Too many requests") is True
        assert is_rate_limit_error("HTTP 429 Too Many Requests") is True
        assert is_rate_limit_error("API quota exceeded") is True
        assert is_rate_limit_error("Server is overloaded") is True

    def test_specific_429_patterns(self):
        """Test that 429 is detected with proper context."""
        assert is_rate_limit_error("http 429") is True
        assert is_rate_limit_error("HTTP429") is True
        assert is_rate_limit_error("status 429") is True
        assert is_rate_limit_error("error 429") is True
        assert is_rate_limit_error("429 too many requests") is True

    def test_case_insensitive(self):
        """Test that detection is case-insensitive."""
        assert is_rate_limit_error("RATE LIMIT") is True
        assert is_rate_limit_error("Rate Limit") is True
        assert is_rate_limit_error("rate limit") is True
        assert is_rate_limit_error("RaTe LiMiT") is True

    def test_non_rate_limit_errors(self):
        """Test non-rate-limit error messages."""
        assert is_rate_limit_error("Connection refused") is False
        assert is_rate_limit_error("Authentication failed") is False
        assert is_rate_limit_error("Invalid API key") is False
        assert is_rate_limit_error("Internal server error") is False
        assert is_rate_limit_error("Network timeout") is False
        assert is_rate_limit_error("") is False


class TestFalsePositives(unittest.TestCase):
    """Verify non-rate-limit messages don't trigger detection."""

    def test_version_numbers_with_429(self):
        """Version numbers should not trigger."""
        assert is_rate_limit_error("Node v14.29.0") is False
        assert is_rate_limit_error("Python 3.12.429") is False
        assert is_rate_limit_error("Version 2.429 released") is False

    def test_issue_and_pr_numbers(self):
        """Issue/PR numbers should not trigger."""
        assert is_rate_limit_error("See PR #429") is False
        assert is_rate_limit_error("Fixed in issue 429") is False
        assert is_rate_limit_error("Closes #429") is False

    def test_line_numbers(self):
        """Line numbers in errors should not trigger."""
        assert is_rate_limit_error("Error at line 429") is False
        assert is_rate_limit_error("See file.py:429") is False

    def test_port_numbers(self):
        """Port numbers should not trigger."""
        assert is_rate_limit_error("port 4293") is False
        assert is_rate_limit_error("localhost:4290") is False

    def test_legitimate_wait_messages(self):
        """Legitimate wait instructions should not trigger."""
        # These would fail if "please wait" pattern still exists
        assert is_rate_limit_error("Please wait for the build to complete") is False
        assert is_rate_limit_error("Please wait while I analyze this") is False

    def test_retry_discussion_messages(self):
        """Messages discussing retry logic should not trigger."""
        # These would fail if "try again later" pattern still exists
        assert is_rate_limit_error("Try again later after maintenance") is False
        assert is_rate_limit_error("The user should try again later") is False

    def test_limit_discussion_messages(self):
        """Messages discussing limits should not trigger (removed pattern)."""
        # These would fail if "limit reached" pattern still exists
        assert is_rate_limit_error("File size limit reached") is False
        assert is_rate_limit_error("Memory limit reached, consider optimization") is False

    def test_overloaded_in_programming_context(self):
        """Method/operator overloading discussions should not trigger."""
        assert is_rate_limit_error("I will create an overloaded constructor") is False
        assert is_rate_limit_error("The + operator is overloaded") is False
        assert is_rate_limit_error("Here is the overloaded version of the function") is False
        assert is_rate_limit_error("The method is overloaded to accept different types") is False
        # But actual API overload messages should still match
        assert is_rate_limit_error("Server is overloaded") is True
        assert is_rate_limit_error("API overloaded") is True
        assert is_rate_limit_error("system is overloaded") is True


class TestUsageLimitDetection(unittest.TestCase):
    """Claude subscription usage-limit messages (issue #19)."""

    def test_claude_code_limit_messages(self):
        assert is_rate_limit_error(
            "Limit reached · resets 6pm (America/New_York) · /upgrade to Max or turn on /extra-usage"
        ) is True
        assert is_rate_limit_error("5-hour limit reached ∙ resets 1pm") is True
        assert is_rate_limit_error("You've hit your limit · resets 3am (Europe/London)") is True
        assert is_rate_limit_error("Claude AI usage limit reached|1760000000") is True
        assert is_rate_limit_error("Claude usage limit reached. Your limit will reset at 3pm") is True

    def test_generic_limit_text_not_matched(self):
        assert is_rate_limit_error("File size limit reached") is False
        assert is_rate_limit_error("Added a check: when the upload limit is reached we show a toast") is False
        assert is_rate_limit_error("Users who hit the limit get a 403") is False


class TestParseLimitReset(unittest.TestCase):
    """Tests for parse_limit_reset()."""

    NY = ZoneInfo("America/New_York")

    def test_time_of_day_with_timezone(self):
        now = datetime(2026, 1, 15, 14, 30, tzinfo=self.NY)
        result = parse_limit_reset("Limit reached · resets 6pm (America/New_York) · /upgrade", now=now)
        assert result is not None
        seconds, target = result
        assert seconds == 3 * 3600 + 30 * 60
        assert target.hour == 18 and target.minute == 0

    def test_minutes_and_reset_at(self):
        now = datetime(2026, 1, 15, 14, 0, tzinfo=self.NY)
        result = parse_limit_reset("Your limit will reset at 6:30 PM (America/New_York).", now=now)
        assert result is not None
        assert result[0] == 4 * 3600 + 30 * 60

    def test_passed_time_rolls_to_tomorrow(self):
        now = datetime(2026, 1, 15, 19, 0, tzinfo=self.NY)
        result = parse_limit_reset("resets 6pm (America/New_York)", now=now)
        assert result is not None
        assert result[0] == 23 * 3600

    def test_twelve_am_pm(self):
        now = datetime(2026, 1, 15, 11, 0, tzinfo=self.NY)
        assert parse_limit_reset("resets 12pm (America/New_York)", now=now)[0] == 3600
        assert parse_limit_reset("resets 12am (America/New_York)", now=now)[0] == 13 * 3600

    def test_other_timezone(self):
        now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)  # London is UTC+0 in January
        result = parse_limit_reset("You've hit your limit · resets 3pm (Europe/London)", now=now)
        assert result is not None
        assert result[0] == 3 * 3600

    def test_unknown_timezone_falls_back(self):
        now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        result = parse_limit_reset("resets 6pm (Not/AZone)", now=now)
        assert result is not None
        assert 1 <= result[0] <= 24 * 3600

    def test_epoch_format(self):
        now = datetime.fromtimestamp(1760000000 - 600, tz=timezone.utc)
        result = parse_limit_reset("Claude AI usage limit reached|1760000000", now=now)
        assert result is not None
        assert result[0] == 600

    def test_no_reset_time(self):
        assert parse_limit_reset("Rate limit exceeded") is None
        assert parse_limit_reset("") is None
        assert parse_limit_reset("resets 13pm") is None


class TestRateLimitMarker(unittest.TestCase):
    """Marker line passed from agent subprocesses to the orchestrator."""

    def test_round_trip(self):
        assert parse_rate_limit_marker(format_rate_limit_marker(3600)) == (True, 3600)
        assert parse_rate_limit_marker(format_rate_limit_marker(None)) == (True, None)
        assert parse_rate_limit_marker(format_rate_limit_marker(42, "extra")) == (True, 42)

    def test_non_marker(self):
        assert parse_rate_limit_marker("Rate limit hit") == (False, None)
        assert parse_rate_limit_marker("") == (False, None)


class TestBackoffFunctions(unittest.TestCase):
    """Test backoff calculation functions from rate_limit_utils."""

    def test_rate_limit_backoff_sequence(self):
        """Test that rate limit backoff follows expected exponential sequence with jitter.

        Base formula: 15 * 2^retries with 0-30% jitter.
        Base values: 15, 30, 60, 120, 240, 480, 960, 1920, 3600, 3600
        With jitter the result should be in [base, base * 1.3].
        """
        base_values = [15, 30, 60, 120, 240, 480, 960, 1920, 3600, 3600]
        for retries, base in enumerate(base_values):
            delay = calculate_rate_limit_backoff(retries)
            # Delay must be at least the base value (jitter is non-negative)
            assert delay >= base, f"Retry {retries}: {delay} < base {base}"
            # Delay must not exceed base + 30% jitter (int truncation means <= base * 1.3)
            max_with_jitter = int(base * 1.3)
            assert delay <= max_with_jitter, f"Retry {retries}: {delay} > max {max_with_jitter}"

    def test_error_backoff_sequence(self):
        """Test that error backoff follows expected linear sequence."""
        expected = [30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 300]  # Caps at 300
        for retries in range(1, len(expected) + 1):
            delay = calculate_error_backoff(retries)
            expected_delay = expected[retries - 1]
            assert delay == expected_delay, f"Retry {retries}: expected {expected_delay}, got {delay}"

    def test_clamp_retry_delay(self):
        """Test that retry delay is clamped to valid range."""
        # Values within range stay the same
        assert clamp_retry_delay(60) == 60
        assert clamp_retry_delay(1800) == 1800
        assert clamp_retry_delay(3600) == 3600

        # Values below minimum get clamped to 1
        assert clamp_retry_delay(0) == 1
        assert clamp_retry_delay(-10) == 1

        # Values above maximum get clamped to 3600
        assert clamp_retry_delay(7200) == 3600
        assert clamp_retry_delay(86400) == 3600


if __name__ == "__main__":
    unittest.main()
