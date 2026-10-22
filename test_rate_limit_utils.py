"""
Unit tests for rate limit handling functions.

Tests the parse_retry_after(), is_rate_limit_error(), and backoff calculation
functions from rate_limit_utils.py (shared module).
"""

import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from rate_limit_utils import (
    USAGE_LIMIT_RESUME_BUFFER_SECONDS,
    calculate_error_backoff,
    calculate_rate_limit_backoff,
    clamp_retry_delay,
    format_usage_limit_banner,
    is_rate_limit_error,
    is_usage_limit_message,
    parse_reset_time,
    parse_retry_after,
    usage_limit_delay_seconds,
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


class TestUsageLimitDetection(unittest.TestCase):
    """Tests for is_usage_limit_message() (Claude subscription caps, issue #19)."""

    def test_cli_usage_limit_messages(self):
        """Messages the Claude CLI prints when a plan limit is hit."""
        messages = [
            "Limit reached · resets 6pm (America/New_York) · /upgrade to Max or turn on /extra-usage",
            "5-hour limit reached ∙ resets 3am",
            "Claude AI usage limit reached|1751234567",
            "You've hit your limit · resets 9pm (Europe/London)",
            "Weekly limit reached ∙ resets Oct 9, 10am",
            "Session limit reached ∙ resets 3pm",
            "Opus limit reached · resets 11am (UTC)",
        ]
        for message in messages:
            assert is_usage_limit_message(message) is True, message
            # Usage limits are also rate limits so existing handling kicks in
            assert is_rate_limit_error(message) is True, message

    def test_usage_limit_within_longer_output(self):
        """The limit line can appear after other agent output."""
        text = "Working on feature...\nLimit reached · resets 6pm (America/New_York)"
        assert is_usage_limit_message(text) is True

    def test_prose_about_limits_does_not_trigger(self):
        """Agent prose mentioning limits must not pause the agent."""
        assert is_usage_limit_message("File size limit reached") is False
        assert is_usage_limit_message("Memory limit reached, consider optimization") is False
        assert is_usage_limit_message("The retry limit reached its maximum") is False
        assert is_usage_limit_message("Show an error when the user has hit your limit") is False
        assert is_usage_limit_message("") is False


class TestParseResetTime(unittest.TestCase):
    """Tests for parse_reset_time()."""

    NY = ZoneInfo("America/New_York")

    def test_reset_later_today(self):
        now = datetime(2026, 10, 22, 13, 15, tzinfo=self.NY)
        target = parse_reset_time("Limit reached · resets 6pm (America/New_York) · /upgrade", now)
        assert target == datetime(2026, 10, 22, 18, 0, tzinfo=self.NY)

    def test_reset_rolls_to_tomorrow(self):
        now = datetime(2026, 10, 22, 19, 0, tzinfo=self.NY)
        target = parse_reset_time("Limit reached · resets 6pm (America/New_York)", now)
        assert target == datetime(2026, 10, 23, 18, 0, tzinfo=self.NY)

    def test_minutes_and_at(self):
        now = datetime(2026, 10, 22, 1, 0, tzinfo=self.NY)
        target = parse_reset_time("resets at 6:30 am (America/New_York)", now)
        assert target == datetime(2026, 10, 22, 6, 30, tzinfo=self.NY)

    def test_twelve_am_and_pm(self):
        now = datetime(2026, 10, 22, 1, 0, tzinfo=self.NY)
        assert parse_reset_time("resets 12am (America/New_York)", now) == datetime(2026, 10, 23, 0, 0, tzinfo=self.NY)
        assert parse_reset_time("resets 12pm (America/New_York)", now) == datetime(2026, 10, 22, 12, 0, tzinfo=self.NY)

    def test_timezone_conversion(self):
        """Reset timezone differs from the local one."""
        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        target = parse_reset_time("resets 6pm (Europe/London)", now)
        assert target is not None
        assert target.astimezone(timezone.utc) == datetime(2026, 10, 22, 17, 0, tzinfo=timezone.utc)

    def test_missing_or_unknown_timezone_uses_local(self):
        now = datetime(2026, 10, 22, 1, 0, tzinfo=timezone.utc)
        assert parse_reset_time("5-hour limit reached ∙ resets 3am", now) == datetime(
            2026, 10, 22, 3, 0, tzinfo=timezone.utc
        )
        assert parse_reset_time("resets 3am (Not/AZone)", now) == datetime(2026, 10, 22, 3, 0, tzinfo=timezone.utc)

    def test_explicit_date(self):
        now = datetime(2026, 10, 6, 9, 0, tzinfo=timezone.utc)
        target = parse_reset_time("Weekly limit reached ∙ resets Oct 9, 10am (UTC)", now)
        assert target == datetime(2026, 10, 9, 10, 0, tzinfo=ZoneInfo("UTC"))

    def test_explicit_date_across_new_year(self):
        now = datetime(2026, 12, 30, 9, 0, tzinfo=timezone.utc)
        target = parse_reset_time("resets Jan 2, 10am (UTC)", now)
        assert target == datetime(2027, 1, 2, 10, 0, tzinfo=ZoneInfo("UTC"))

    def test_epoch_timestamp(self):
        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        reset = now + timedelta(hours=2)
        target = parse_reset_time(f"Claude AI usage limit reached|{int(reset.timestamp())}", now)
        assert target == reset

    def test_unparseable_or_out_of_range(self):
        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        assert parse_reset_time("Rate limit exceeded", now) is None
        assert parse_reset_time("resets 25pm", now) is None
        assert parse_reset_time("resets Foo 9, 10am", now) is None
        # Epoch in the past or too far in the future is ignored
        assert parse_reset_time("usage limit reached|1000000000", now) is None
        far = int((now + timedelta(days=30)).timestamp())
        assert parse_reset_time(f"usage limit reached|{far}", now) is None


class TestUsageLimitDelay(unittest.TestCase):
    """Tests for usage_limit_delay_seconds() and the warning banner."""

    def test_delay_until_reset_plus_buffer(self):
        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        reset = now + timedelta(hours=4, minutes=45)
        expected = 4 * 3600 + 45 * 60 + USAGE_LIMIT_RESUME_BUFFER_SECONDS
        assert usage_limit_delay_seconds(reset, now) == expected

    def test_delay_never_below_one(self):
        now = datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc)
        assert usage_limit_delay_seconds(now - timedelta(hours=1), now) == 1

    def test_banner_mentions_reset(self):
        banner = format_usage_limit_banner("6:00 PM EDT (Oct 22)", 2 * 3600 + 5 * 60)
        assert "USAGE LIMIT REACHED" in banner
        assert "6:00 PM EDT (Oct 22)" in banner
        assert "2h 5m" in banner


if __name__ == "__main__":
    unittest.main()
