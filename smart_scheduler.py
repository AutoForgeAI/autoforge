"""
Smart Scheduler Module
======================

Usage-aware task scheduling based on session/token limits.
Designed for Claude Max accounts where dollar costs aren't relevant,
but session message limits and token consumption matter.

Usage Levels:
- HEALTHY (> 50% remaining)  → Normal operation
- MODERATE (20-50% remaining)→ Focus on completing features
- LOW (5-20% remaining)      → Wind down, finish in-progress only
- CRITICAL (< 5% remaining)  → Stop all new work
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Usage Level Definitions
# =============================================================================


class UsageLevel(Enum):
    """Usage level based on remaining session/token capacity."""
    HEALTHY = "healthy"      # > 50% remaining - normal operation
    MODERATE = "moderate"    # 20-50% remaining - focus on completing features
    LOW = "low"              # 5-20% remaining - wind down mode
    CRITICAL = "critical"    # < 5% remaining - stop all new work


class SchedulingStrategy(Enum):
    """Scheduling strategies based on usage level."""
    FULL_SPEED = "full_speed"          # Normal priority-based scheduling
    COMPLETION_FOCUS = "completion_focus"  # Prioritize nearly-done features
    WIND_DOWN = "wind_down"            # Only complete in-progress tasks
    STOP = "stop"                      # No new tasks


# =============================================================================
# Session Tracking
# =============================================================================


@dataclass
class SessionUsage:
    """Tracks usage within a single Claude session."""
    session_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Message counts
    messages_sent: int = 0
    messages_limit: int = 100  # Claude Max typical limit per session

    # Token tracking
    input_tokens_used: int = 0
    output_tokens_used: int = 0
    context_tokens_used: int = 0
    context_limit: int = 200000  # Context window limit

    # Feature tracking
    features_attempted: int = 0
    features_completed: int = 0

    def message_percentage_used(self) -> float:
        """Percentage of message limit used."""
        if self.messages_limit <= 0:
            return 0.0
        return (self.messages_sent / self.messages_limit) * 100

    def context_percentage_used(self) -> float:
        """Percentage of context window used."""
        if self.context_limit <= 0:
            return 0.0
        return (self.context_tokens_used / self.context_limit) * 100

    def remaining_messages(self) -> int:
        """Messages remaining in session."""
        return max(0, self.messages_limit - self.messages_sent)

    def remaining_context(self) -> int:
        """Context tokens remaining."""
        return max(0, self.context_limit - self.context_tokens_used)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "sessionId": self.session_id,
            "startedAt": self.started_at.isoformat(),
            "messagesSent": self.messages_sent,
            "messagesLimit": self.messages_limit,
            "messagesRemaining": self.remaining_messages(),
            "messagePercentUsed": round(self.message_percentage_used(), 1),
            "inputTokensUsed": self.input_tokens_used,
            "outputTokensUsed": self.output_tokens_used,
            "contextTokensUsed": self.context_tokens_used,
            "contextLimit": self.context_limit,
            "contextRemaining": self.remaining_context(),
            "contextPercentUsed": round(self.context_percentage_used(), 1),
            "featuresAttempted": self.features_attempted,
            "featuresCompleted": self.features_completed,
        }


@dataclass
class UsageSnapshot:
    """Point-in-time snapshot of usage state."""
    timestamp: datetime
    level: UsageLevel
    strategy: SchedulingStrategy
    session: SessionUsage

    # Derived metrics
    overall_percentage_used: float  # Max of message and context percentages
    should_continue: bool
    recommended_concurrency: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "strategy": self.strategy.value,
            "session": self.session.to_dict(),
            "overallPercentageUsed": round(self.overall_percentage_used, 1),
            "shouldContinue": self.should_continue,
            "recommendedConcurrency": self.recommended_concurrency,
        }


# =============================================================================
# Smart Scheduler
# =============================================================================


class SmartScheduler:
    """
    Usage-aware task scheduler.

    Adjusts scheduling behavior based on session/token usage levels.
    Designed for Claude Max accounts where session limits matter more than costs.
    """

    # Map usage levels to scheduling strategies
    LEVEL_TO_STRATEGY: dict[UsageLevel, SchedulingStrategy] = {
        UsageLevel.HEALTHY: SchedulingStrategy.FULL_SPEED,
        UsageLevel.MODERATE: SchedulingStrategy.COMPLETION_FOCUS,
        UsageLevel.LOW: SchedulingStrategy.WIND_DOWN,
        UsageLevel.CRITICAL: SchedulingStrategy.STOP,
    }

    # Recommended concurrency by usage level
    LEVEL_TO_CONCURRENCY: dict[UsageLevel, int] = {
        UsageLevel.HEALTHY: 4,
        UsageLevel.MODERATE: 2,
        UsageLevel.LOW: 1,
        UsageLevel.CRITICAL: 0,
    }

    def __init__(
        self,
        session_id: str | None = None,
        messages_limit: int = 100,
        context_limit: int = 200000,
    ):
        """
        Initialize the smart scheduler.

        Args:
            session_id: Optional session identifier
            messages_limit: Maximum messages per session (Claude Max limit)
            context_limit: Maximum context tokens (model's context window)
        """
        self.session = SessionUsage(
            session_id=session_id or f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            messages_limit=messages_limit,
            context_limit=context_limit,
        )

    def record_message(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        context_tokens: int = 0,
    ) -> None:
        """
        Record a message exchange.

        Args:
            input_tokens: Tokens in the input message
            output_tokens: Tokens in the output response
            context_tokens: Current context size
        """
        self.session.messages_sent += 1
        self.session.input_tokens_used += input_tokens
        self.session.output_tokens_used += output_tokens
        self.session.context_tokens_used = max(
            self.session.context_tokens_used,
            context_tokens
        )

        logger.debug(
            "Recorded message: %d/%d messages, %d/%d context",
            self.session.messages_sent,
            self.session.messages_limit,
            self.session.context_tokens_used,
            self.session.context_limit,
        )

    def record_feature_attempt(self, completed: bool = False) -> None:
        """Record a feature implementation attempt."""
        self.session.features_attempted += 1
        if completed:
            self.session.features_completed += 1

    def get_usage_level(self) -> UsageLevel:
        """
        Determine current usage level based on remaining capacity.

        Uses the more restrictive of message or context limits.
        """
        # Calculate remaining percentages
        message_remaining_pct = 100 - self.session.message_percentage_used()
        context_remaining_pct = 100 - self.session.context_percentage_used()

        # Use the more restrictive (lower) remaining percentage
        remaining_pct = min(message_remaining_pct, context_remaining_pct)

        if remaining_pct < 5:
            return UsageLevel.CRITICAL
        elif remaining_pct < 20:
            return UsageLevel.LOW
        elif remaining_pct < 50:
            return UsageLevel.MODERATE
        return UsageLevel.HEALTHY

    def get_strategy(self) -> SchedulingStrategy:
        """Get current scheduling strategy based on usage level."""
        level = self.get_usage_level()
        return self.LEVEL_TO_STRATEGY[level]

    def get_recommended_concurrency(self) -> int:
        """Get recommended number of concurrent agents."""
        level = self.get_usage_level()
        return self.LEVEL_TO_CONCURRENCY[level]

    def should_allow_new_work(self) -> bool:
        """Check if new work should be started."""
        strategy = self.get_strategy()
        return strategy != SchedulingStrategy.STOP

    def should_prioritize_completion(self) -> bool:
        """Check if we should prioritize completing near-done features."""
        strategy = self.get_strategy()
        return strategy in (
            SchedulingStrategy.COMPLETION_FOCUS,
            SchedulingStrategy.WIND_DOWN,
        )

    def should_only_finish_in_progress(self) -> bool:
        """Check if we should only work on in-progress tasks."""
        strategy = self.get_strategy()
        return strategy == SchedulingStrategy.WIND_DOWN

    def get_snapshot(self) -> UsageSnapshot:
        """Get current usage snapshot."""
        level = self.get_usage_level()
        strategy = self.get_strategy()

        overall_pct = max(
            self.session.message_percentage_used(),
            self.session.context_percentage_used(),
        )

        return UsageSnapshot(
            timestamp=datetime.now(timezone.utc),
            level=level,
            strategy=strategy,
            session=self.session,
            overall_percentage_used=overall_pct,
            should_continue=self.should_allow_new_work(),
            recommended_concurrency=self.get_recommended_concurrency(),
        )

    def get_status_message(self) -> str:
        """Get human-readable status message."""
        level = self.get_usage_level()
        snapshot = self.get_snapshot()

        messages = {
            UsageLevel.HEALTHY: (
                f"✓ Healthy - {snapshot.session.remaining_messages()} messages remaining, "
                f"running at full speed"
            ),
            UsageLevel.MODERATE: (
                f"◐ Moderate usage - {snapshot.session.remaining_messages()} messages remaining, "
                f"focusing on completing features"
            ),
            UsageLevel.LOW: (
                f"◑ Low capacity - {snapshot.session.remaining_messages()} messages remaining, "
                f"finishing in-progress tasks only"
            ),
            UsageLevel.CRITICAL: (
                f"✗ Critical - {snapshot.session.remaining_messages()} messages remaining, "
                f"work paused"
            ),
        }

        return messages.get(level, "Unknown status")

    def reset_session(
        self,
        session_id: str | None = None,
        preserve_limits: bool = True,
    ) -> None:
        """
        Reset session tracking for a new session.

        Args:
            session_id: New session ID (auto-generated if None)
            preserve_limits: Whether to preserve the current limits
        """
        old_limits = (self.session.messages_limit, self.session.context_limit)

        self.session = SessionUsage(
            session_id=session_id or f"session_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            messages_limit=old_limits[0] if preserve_limits else 100,
            context_limit=old_limits[1] if preserve_limits else 200000,
        )

        logger.info("Session reset: %s", self.session.session_id)


# =============================================================================
# Global Scheduler Instance
# =============================================================================

_schedulers: dict[str, SmartScheduler] = {}


def get_scheduler(project_name: str) -> SmartScheduler:
    """
    Get or create a SmartScheduler for a project.

    Args:
        project_name: Name of the project

    Returns:
        SmartScheduler instance for the project
    """
    if project_name not in _schedulers:
        _schedulers[project_name] = SmartScheduler()
    return _schedulers[project_name]


def reset_scheduler(project_name: str) -> None:
    """Reset the scheduler for a project."""
    if project_name in _schedulers:
        _schedulers[project_name].reset_session()


def get_all_schedulers() -> dict[str, SmartScheduler]:
    """Get all active schedulers."""
    return _schedulers.copy()
