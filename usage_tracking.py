"""
Usage Tracking
==============

Track and analyze Claude API usage across projects and sessions.

Features:
- Capture usage from API responses
- Store in UsageLog table
- Calculate daily/weekly/monthly aggregates
- Smart task scheduling based on remaining usage
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.database import UsageLog, create_database


class UsageLevel(Enum):
    """Usage level categories for smart scheduling."""

    CRITICAL = "critical"  # < 5% remaining
    LOW = "low"  # 5-20% remaining
    MODERATE = "moderate"  # 20-50% remaining
    HEALTHY = "healthy"  # > 50% remaining


@dataclass
class UsageStats:
    """Aggregated usage statistics."""

    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    total_cost: float
    session_count: int
    average_tokens_per_session: float
    period_start: datetime
    period_end: datetime


@dataclass
class UsageLimits:
    """Usage limits configuration."""

    daily_token_limit: int = 1_000_000  # 1M tokens/day default
    monthly_token_limit: int = 25_000_000  # 25M tokens/month default
    cost_limit_daily: float = 50.0  # $50/day default
    cost_limit_monthly: float = 1000.0  # $1000/month default


# Approximate token costs (Claude 3.5 Sonnet pricing)
INPUT_TOKEN_COST = 3.0 / 1_000_000  # $3 per 1M input tokens
OUTPUT_TOKEN_COST = 15.0 / 1_000_000  # $15 per 1M output tokens


def calculate_cost(input_tokens: int, output_tokens: int) -> float:
    """Calculate approximate cost from token counts."""
    return (input_tokens * INPUT_TOKEN_COST) + (output_tokens * OUTPUT_TOKEN_COST)


class UsageTracker:
    """Track and analyze API usage."""

    def __init__(self, project_dir: Path, limits: Optional[UsageLimits] = None):
        """
        Initialize the usage tracker.

        Args:
            project_dir: Path to the project directory
            limits: Optional custom usage limits
        """
        self.project_dir = project_dir
        self.limits = limits or UsageLimits()
        self._engine, self._session_maker = create_database(project_dir)

    def _get_session(self) -> Session:
        """Get a database session."""
        return self._session_maker()

    def record_usage(
        self,
        project_name: str,
        session_id: str,
        agent_type: str,
        input_tokens: int,
        output_tokens: int,
        model: str = "claude-3-5-sonnet",
        metadata: Optional[dict] = None,
    ) -> UsageLog:
        """
        Record a usage event.

        Args:
            project_name: Name of the project
            session_id: Unique session identifier
            agent_type: Type of agent (coding, reviewer, etc.)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model used
            metadata: Optional additional data

        Returns:
            The created UsageLog entry
        """
        db = self._get_session()
        try:
            cost = calculate_cost(input_tokens, output_tokens)

            usage = UsageLog(
                project_name=project_name,
                session_id=session_id,
                agent_type=agent_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost=cost,
                model=model,
                metadata=metadata or {},
            )

            db.add(usage)
            db.commit()
            db.refresh(usage)
            return usage
        finally:
            db.close()

    def get_daily_usage(
        self,
        project_name: Optional[str] = None,
        date: Optional[datetime] = None,
    ) -> UsageStats:
        """
        Get usage statistics for a specific day.

        Args:
            project_name: Optional filter by project
            date: Date to check (defaults to today)

        Returns:
            UsageStats for the day
        """
        if date is None:
            date = datetime.utcnow()

        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        return self._get_usage_for_period(project_name, start, end)

    def get_weekly_usage(
        self,
        project_name: Optional[str] = None,
        week_start: Optional[datetime] = None,
    ) -> UsageStats:
        """
        Get usage statistics for a week.

        Args:
            project_name: Optional filter by project
            week_start: Start of week (defaults to current week)

        Returns:
            UsageStats for the week
        """
        if week_start is None:
            today = datetime.utcnow()
            week_start = today - timedelta(days=today.weekday())

        start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)

        return self._get_usage_for_period(project_name, start, end)

    def get_monthly_usage(
        self,
        project_name: Optional[str] = None,
        month: Optional[datetime] = None,
    ) -> UsageStats:
        """
        Get usage statistics for a month.

        Args:
            project_name: Optional filter by project
            month: Any date in the month (defaults to current month)

        Returns:
            UsageStats for the month
        """
        if month is None:
            month = datetime.utcnow()

        start = month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if month.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)

        return self._get_usage_for_period(project_name, start, end)

    def _get_usage_for_period(
        self,
        project_name: Optional[str],
        start: datetime,
        end: datetime,
    ) -> UsageStats:
        """Get usage statistics for a time period."""
        db = self._get_session()
        try:
            query = db.query(
                func.sum(UsageLog.input_tokens).label("input_tokens"),
                func.sum(UsageLog.output_tokens).label("output_tokens"),
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.cost).label("cost"),
                func.count(func.distinct(UsageLog.session_id)).label("sessions"),
            ).filter(
                UsageLog.timestamp >= start,
                UsageLog.timestamp < end,
            )

            if project_name:
                query = query.filter(UsageLog.project_name == project_name)

            result = query.first()

            total_tokens = result.total_tokens or 0
            session_count = result.sessions or 0

            return UsageStats(
                total_input_tokens=result.input_tokens or 0,
                total_output_tokens=result.output_tokens or 0,
                total_tokens=total_tokens,
                total_cost=result.cost or 0.0,
                session_count=session_count,
                average_tokens_per_session=(
                    total_tokens / session_count if session_count > 0 else 0
                ),
                period_start=start,
                period_end=end,
            )
        finally:
            db.close()

    def get_usage_level(self, project_name: Optional[str] = None) -> UsageLevel:
        """
        Determine current usage level based on daily and monthly limits.

        Returns the most restrictive level.
        """
        daily = self.get_daily_usage(project_name)
        monthly = self.get_monthly_usage(project_name)

        # Check daily limits
        daily_token_pct = daily.total_tokens / self.limits.daily_token_limit
        daily_cost_pct = daily.total_cost / self.limits.cost_limit_daily

        # Check monthly limits
        monthly_token_pct = monthly.total_tokens / self.limits.monthly_token_limit
        monthly_cost_pct = monthly.total_cost / self.limits.cost_limit_monthly

        # Use the highest percentage (most restrictive)
        max_pct = max(daily_token_pct, daily_cost_pct, monthly_token_pct, monthly_cost_pct)
        remaining_pct = (1 - max_pct) * 100

        if remaining_pct < 5:
            return UsageLevel.CRITICAL
        elif remaining_pct < 20:
            return UsageLevel.LOW
        elif remaining_pct < 50:
            return UsageLevel.MODERATE
        else:
            return UsageLevel.HEALTHY

    def get_remaining_budget(self, project_name: Optional[str] = None) -> dict:
        """
        Get remaining budget for today and this month.

        Returns:
            Dict with daily and monthly remaining tokens and cost
        """
        daily = self.get_daily_usage(project_name)
        monthly = self.get_monthly_usage(project_name)

        return {
            "daily": {
                "tokens_used": daily.total_tokens,
                "tokens_remaining": max(0, self.limits.daily_token_limit - daily.total_tokens),
                "tokens_limit": self.limits.daily_token_limit,
                "cost_used": daily.total_cost,
                "cost_remaining": max(0, self.limits.cost_limit_daily - daily.total_cost),
                "cost_limit": self.limits.cost_limit_daily,
                "percentage_used": (daily.total_tokens / self.limits.daily_token_limit) * 100,
            },
            "monthly": {
                "tokens_used": monthly.total_tokens,
                "tokens_remaining": max(0, self.limits.monthly_token_limit - monthly.total_tokens),
                "tokens_limit": self.limits.monthly_token_limit,
                "cost_used": monthly.total_cost,
                "cost_remaining": max(0, self.limits.cost_limit_monthly - monthly.total_cost),
                "cost_limit": self.limits.cost_limit_monthly,
                "percentage_used": (monthly.total_tokens / self.limits.monthly_token_limit) * 100,
            },
            "level": self.get_usage_level(project_name).value,
        }

    def get_usage_by_project(self, days: int = 30) -> list[dict]:
        """
        Get usage breakdown by project for the last N days.

        Returns:
            List of dicts with project usage stats
        """
        db = self._get_session()
        try:
            start = datetime.utcnow() - timedelta(days=days)

            results = (
                db.query(
                    UsageLog.project_name,
                    func.sum(UsageLog.total_tokens).label("total_tokens"),
                    func.sum(UsageLog.cost).label("cost"),
                    func.count(func.distinct(UsageLog.session_id)).label("sessions"),
                )
                .filter(UsageLog.timestamp >= start)
                .group_by(UsageLog.project_name)
                .order_by(func.sum(UsageLog.total_tokens).desc())
                .all()
            )

            return [
                {
                    "project_name": r.project_name,
                    "total_tokens": r.total_tokens or 0,
                    "cost": r.cost or 0.0,
                    "sessions": r.sessions or 0,
                }
                for r in results
            ]
        finally:
            db.close()

    def get_usage_by_agent(
        self,
        project_name: Optional[str] = None,
        days: int = 30,
    ) -> list[dict]:
        """
        Get usage breakdown by agent type.

        Returns:
            List of dicts with agent type usage stats
        """
        db = self._get_session()
        try:
            start = datetime.utcnow() - timedelta(days=days)

            query = db.query(
                UsageLog.agent_type,
                func.sum(UsageLog.total_tokens).label("total_tokens"),
                func.sum(UsageLog.cost).label("cost"),
                func.count().label("calls"),
            ).filter(UsageLog.timestamp >= start)

            if project_name:
                query = query.filter(UsageLog.project_name == project_name)

            results = (
                query.group_by(UsageLog.agent_type)
                .order_by(func.sum(UsageLog.total_tokens).desc())
                .all()
            )

            return [
                {
                    "agent_type": r.agent_type,
                    "total_tokens": r.total_tokens or 0,
                    "cost": r.cost or 0.0,
                    "calls": r.calls or 0,
                }
                for r in results
            ]
        finally:
            db.close()

    def get_usage_timeline(
        self,
        project_name: Optional[str] = None,
        days: int = 14,
    ) -> list[dict]:
        """
        Get daily usage for the last N days.

        Returns:
            List of dicts with daily usage for charting
        """
        results = []
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(days - 1, -1, -1):
            date = today - timedelta(days=i)
            stats = self.get_daily_usage(project_name, date)
            results.append({
                "date": date.strftime("%Y-%m-%d"),
                "tokens": stats.total_tokens,
                "cost": stats.total_cost,
                "sessions": stats.session_count,
            })

        return results
