"""
Smart Task Scheduler
====================

Intelligently schedules tasks based on usage levels and project state.

Features:
- Prioritize completion tasks when usage is low
- Graceful wind-down at critical usage levels
- Balance work across phases
- Consider task complexity for token estimation
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from api.database import Task, Phase, Feature, create_database, get_ready_tasks
from usage_tracking import UsageTracker, UsageLevel


class SchedulingStrategy(Enum):
    """Scheduling strategy based on usage level."""

    FULL_SPEED = "full_speed"  # Normal operation
    COMPLETION_FOCUS = "completion_focus"  # Prioritize nearly-done tasks
    WIND_DOWN = "wind_down"  # Finish current, avoid starting new
    STOP = "stop"  # Critical usage, stop new work


@dataclass
class ScheduledTask:
    """A task scheduled for execution with metadata."""

    task: Task
    priority_score: float
    reason: str
    estimated_tokens: int


class SmartTaskScheduler:
    """
    Intelligently schedules tasks based on usage and project state.

    Strategies:
    - FULL_SPEED: Normal scheduling by priority
    - COMPLETION_FOCUS: Prefer tasks in features that are almost done
    - WIND_DOWN: Only work on tasks that are in-progress, skip new ones
    - STOP: Don't schedule any new tasks
    """

    # Estimated tokens per task complexity
    COMPLEXITY_TOKEN_ESTIMATES = {
        1: 5_000,  # Simple task
        2: 10_000,  # Moderate task
        3: 20_000,  # Complex task
        4: 35_000,  # Very complex task
        5: 50_000,  # Extremely complex task
    }

    def __init__(self, project_dir: Path):
        """
        Initialize the scheduler.

        Args:
            project_dir: Path to the project directory
        """
        self.project_dir = project_dir
        self._engine, self._session_maker = create_database(project_dir)
        self.usage_tracker = UsageTracker(project_dir)

    def _get_session(self) -> Session:
        """Get a database session."""
        return self._session_maker()

    def get_strategy(self) -> SchedulingStrategy:
        """
        Determine the current scheduling strategy based on usage level.

        Returns:
            The appropriate SchedulingStrategy
        """
        level = self.usage_tracker.get_usage_level()

        if level == UsageLevel.CRITICAL:
            return SchedulingStrategy.STOP
        elif level == UsageLevel.LOW:
            return SchedulingStrategy.WIND_DOWN
        elif level == UsageLevel.MODERATE:
            return SchedulingStrategy.COMPLETION_FOCUS
        else:
            return SchedulingStrategy.FULL_SPEED

    def estimate_tokens(self, task: Task) -> int:
        """
        Estimate tokens needed to complete a task.

        Args:
            task: The task to estimate

        Returns:
            Estimated token count
        """
        complexity = task.estimated_complexity or 2  # Default to moderate
        base_estimate = self.COMPLEXITY_TOKEN_ESTIMATES.get(complexity, 20_000)

        # Adjust based on step count
        step_count = len(task.steps) if task.steps else 3
        step_multiplier = 1 + (step_count - 3) * 0.1  # +10% per step over 3

        return int(base_estimate * max(0.5, min(2.0, step_multiplier)))

    def get_feature_completion_score(self, db: Session, task: Task) -> float:
        """
        Calculate how close the task's feature is to completion.

        Returns a score from 0 to 1, where 1 means the feature is almost done.
        """
        if not task.feature_id:
            return 0.5  # No feature context

        feature = db.query(Feature).filter(Feature.id == task.feature_id).first()
        if not feature:
            return 0.5

        total_tasks = len(feature.tasks)
        if total_tasks == 0:
            return 0.5

        passing_tasks = sum(1 for t in feature.tasks if t.passes)
        return passing_tasks / total_tasks

    def get_phase_priority_score(self, db: Session, task: Task) -> float:
        """
        Calculate priority based on phase order.

        Earlier phases get higher priority.
        """
        if not task.feature_id:
            return 0.5

        feature = db.query(Feature).filter(Feature.id == task.feature_id).first()
        if not feature or not feature.phase_id:
            return 0.5

        phase = db.query(Phase).filter(Phase.id == feature.phase_id).first()
        if not phase:
            return 0.5

        # Count total phases
        total_phases = db.query(Phase).filter(Phase.project_name == phase.project_name).count()
        if total_phases == 0:
            return 0.5

        # Earlier phases (lower order) get higher score
        return 1 - (phase.order / total_phases)

    def score_task(
        self,
        db: Session,
        task: Task,
        strategy: SchedulingStrategy,
    ) -> tuple[float, str]:
        """
        Score a task for scheduling.

        Higher scores = higher priority.

        Returns:
            Tuple of (score, reason)
        """
        # Base score from task priority (inverted - lower priority number = higher score)
        max_priority = 1000  # Assume max priority
        base_score = (max_priority - task.priority) / max_priority

        # Factor in feature completion
        completion_score = self.get_feature_completion_score(db, task)

        # Factor in phase priority
        phase_score = self.get_phase_priority_score(db, task)

        # Combine scores based on strategy
        if strategy == SchedulingStrategy.FULL_SPEED:
            # Normal: priority matters most
            final_score = base_score * 0.6 + phase_score * 0.3 + completion_score * 0.1
            reason = "Standard priority scheduling"

        elif strategy == SchedulingStrategy.COMPLETION_FOCUS:
            # Completion focus: prioritize nearly-done features
            final_score = base_score * 0.3 + phase_score * 0.2 + completion_score * 0.5
            reason = f"Feature is {completion_score:.0%} complete"

        elif strategy == SchedulingStrategy.WIND_DOWN:
            # Wind down: only in-progress tasks, heavily weight completion
            if task.in_progress:
                final_score = 1.0 + completion_score  # Boost in-progress
                reason = "Completing in-progress task"
            else:
                final_score = -1.0  # Deprioritize new work
                reason = "Wind-down: avoiding new tasks"

        else:  # STOP
            final_score = -1.0
            reason = "Usage critical: no new tasks"

        return final_score, reason

    def get_next_task(
        self,
        project_name: Optional[str] = None,
    ) -> Optional[ScheduledTask]:
        """
        Get the next task to work on considering usage and priorities.

        Args:
            project_name: Optional filter by project

        Returns:
            ScheduledTask or None if no tasks should be scheduled
        """
        strategy = self.get_strategy()

        if strategy == SchedulingStrategy.STOP:
            return None

        db = self._get_session()
        try:
            # Get ready tasks
            ready_tasks = get_ready_tasks(db, limit=20)

            if not ready_tasks:
                return None

            # Score all tasks
            scored_tasks = []
            for task in ready_tasks:
                score, reason = self.score_task(db, task, strategy)
                if score >= 0:  # Only include positive-scored tasks
                    scored_tasks.append((task, score, reason))

            if not scored_tasks:
                return None

            # Sort by score (highest first)
            scored_tasks.sort(key=lambda x: x[1], reverse=True)

            # Return best task
            best_task, score, reason = scored_tasks[0]
            return ScheduledTask(
                task=best_task,
                priority_score=score,
                reason=reason,
                estimated_tokens=self.estimate_tokens(best_task),
            )
        finally:
            db.close()

    def get_scheduling_recommendation(
        self,
        project_name: Optional[str] = None,
    ) -> dict:
        """
        Get a scheduling recommendation with context.

        Returns:
            Dict with scheduling info and recommendations
        """
        strategy = self.get_strategy()
        usage = self.usage_tracker.get_remaining_budget(project_name)
        next_task = self.get_next_task(project_name)

        recommendations = []

        if strategy == SchedulingStrategy.STOP:
            recommendations.append("Usage is critical. Stop all new work.")
            recommendations.append("Consider waiting until tomorrow for usage reset.")

        elif strategy == SchedulingStrategy.WIND_DOWN:
            recommendations.append("Usage is low. Finish in-progress tasks only.")
            recommendations.append("Avoid starting new features or complex tasks.")

        elif strategy == SchedulingStrategy.COMPLETION_FOCUS:
            recommendations.append("Usage is moderate. Focus on completing features.")
            recommendations.append("Prioritize tasks in nearly-complete features.")

        else:
            recommendations.append("Usage is healthy. Normal operation.")

        return {
            "strategy": strategy.value,
            "usage_level": usage["level"],
            "daily_remaining_tokens": usage["daily"]["tokens_remaining"],
            "daily_percentage_used": usage["daily"]["percentage_used"],
            "monthly_remaining_tokens": usage["monthly"]["tokens_remaining"],
            "monthly_percentage_used": usage["monthly"]["percentage_used"],
            "next_task": {
                "id": next_task.task.id,
                "name": next_task.task.name,
                "priority_score": next_task.priority_score,
                "reason": next_task.reason,
                "estimated_tokens": next_task.estimated_tokens,
            } if next_task else None,
            "recommendations": recommendations,
            "can_proceed": strategy != SchedulingStrategy.STOP,
        }

    def should_continue_session(
        self,
        current_session_tokens: int,
        tasks_completed: int,
    ) -> tuple[bool, str]:
        """
        Determine if the agent should continue or end the session.

        Args:
            current_session_tokens: Tokens used in current session
            tasks_completed: Number of tasks completed this session

        Returns:
            Tuple of (should_continue, reason)
        """
        strategy = self.get_strategy()

        if strategy == SchedulingStrategy.STOP:
            return False, "Usage critical - ending session"

        if strategy == SchedulingStrategy.WIND_DOWN:
            if tasks_completed > 0:
                return False, "Wind-down mode - session complete after finishing task"
            # Continue to finish in-progress work
            return True, "Finishing in-progress work"

        # Check if session is getting long
        if current_session_tokens > 100_000:  # ~100k tokens is a long session
            return False, "Session reaching token limit"

        # Default: continue
        return True, "Session can continue"
