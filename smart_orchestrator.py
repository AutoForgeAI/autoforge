"""
Smart Orchestrator
==================

Enhanced orchestrator with learning capabilities that tracks feature success
patterns and optimizes model selection and retry strategies.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import JSON

logger = logging.getLogger(__name__)

Base = declarative_base()


def _utc_now() -> datetime:
    """Return current UTC time."""
    return datetime.now(timezone.utc)


# =============================================================================
# Learning Database Models
# =============================================================================


class FeaturePattern(Base):
    """
    Tracks patterns in feature implementations to learn optimal strategies.

    This helps the orchestrator:
    - Identify which models work best for certain feature categories
    - Predict feature difficulty and adjust retries
    - Optimize token usage based on historical patterns
    """

    __tablename__ = "feature_patterns"

    __table_args__ = (
        Index("ix_pattern_category", "category"),
        Index("ix_pattern_model", "model_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False, index=True)

    # Success tracking
    total_attempts = Column(Integer, nullable=False, default=0)
    successful_attempts = Column(Integer, nullable=False, default=0)
    avg_attempts_to_success = Column(Float, nullable=False, default=1.0)

    # Model performance
    model_id = Column(String(100), nullable=True)  # Best performing model
    model_success_rate = Column(Float, nullable=False, default=0.0)

    # Resource patterns
    avg_input_tokens = Column(Integer, nullable=False, default=0)
    avg_output_tokens = Column(Integer, nullable=False, default=0)
    avg_cost = Column(Float, nullable=False, default=0.0)
    avg_duration_ms = Column(Integer, nullable=False, default=0)

    # Complexity indicators
    avg_steps = Column(Float, nullable=False, default=1.0)
    estimated_difficulty = Column(Float, nullable=False, default=0.5)  # 0-1 scale

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "category": self.category,
            "totalAttempts": self.total_attempts,
            "successfulAttempts": self.successful_attempts,
            "successRate": round(self.successful_attempts / self.total_attempts * 100, 1) if self.total_attempts > 0 else 0,
            "avgAttemptsToSuccess": round(self.avg_attempts_to_success, 2),
            "bestModel": self.model_id,
            "modelSuccessRate": round(self.model_success_rate * 100, 1),
            "avgInputTokens": self.avg_input_tokens,
            "avgOutputTokens": self.avg_output_tokens,
            "avgCost": round(self.avg_cost, 4),
            "avgDurationMs": self.avg_duration_ms,
            "estimatedDifficulty": round(self.estimated_difficulty, 2),
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class ModelPerformance(Base):
    """
    Tracks model performance across different contexts.

    Helps the orchestrator select the optimal model based on:
    - Feature category
    - Historical success rates
    - Cost efficiency
    """

    __tablename__ = "model_performance"

    __table_args__ = (
        Index("ix_perf_model_category", "model_id", "category"),
    )

    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(String(100), nullable=False, index=True)
    category = Column(String(100), nullable=True)  # NULL = overall performance

    # Performance metrics
    total_attempts = Column(Integer, nullable=False, default=0)
    successful_attempts = Column(Integer, nullable=False, default=0)
    success_rate = Column(Float, nullable=False, default=0.0)

    # Resource efficiency
    total_input_tokens = Column(Integer, nullable=False, default=0)
    total_output_tokens = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)
    cost_per_success = Column(Float, nullable=False, default=0.0)

    # Timing
    avg_duration_ms = Column(Integer, nullable=False, default=0)

    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "modelId": self.model_id,
            "category": self.category,
            "totalAttempts": self.total_attempts,
            "successfulAttempts": self.successful_attempts,
            "successRate": round(self.success_rate * 100, 1),
            "totalInputTokens": self.total_input_tokens,
            "totalOutputTokens": self.total_output_tokens,
            "totalCost": round(self.total_cost, 4),
            "costPerSuccess": round(self.cost_per_success, 4),
            "avgDurationMs": self.avg_duration_ms,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class LearningInsight(Base):
    """
    Stores actionable insights derived from learning.

    These insights can be surfaced to users or used for auto-optimization.
    """

    __tablename__ = "learning_insights"

    id = Column(Integer, primary_key=True, index=True)
    insight_type = Column(String(50), nullable=False)  # model_recommendation, retry_strategy, etc.
    category = Column(String(100), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.5)  # 0-1 scale
    data = Column(JSON, nullable=True)  # Additional structured data
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    applied = Column(Integer, nullable=False, default=0)  # Has this been applied?

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "insightType": self.insight_type,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "data": self.data,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "applied": bool(self.applied),
        }


# =============================================================================
# Smart Orchestrator Service
# =============================================================================


@dataclass
class FeatureRecommendation:
    """Recommendation for implementing a feature."""
    recommended_model: str
    expected_attempts: int
    estimated_cost: float
    estimated_duration_ms: int
    difficulty: float
    confidence: float
    reasoning: str


@dataclass
class OrchestratorConfig:
    """Configuration for the smart orchestrator."""
    default_model: str = "claude-opus-4-5-20251101"
    fallback_model: str = "claude-sonnet-4-5-20250929"
    max_retries: int = 3
    learning_threshold: int = 5  # Min samples before making recommendations
    cost_weight: float = 0.3  # Weight for cost in optimization (vs success rate)
    auto_optimize: bool = False  # Auto-apply learned optimizations


class SmartOrchestrator:
    """
    Orchestrator with learning capabilities.

    Features:
    - Tracks feature implementation patterns
    - Learns optimal model selection per category
    - Predicts feature difficulty
    - Generates actionable insights
    - Optimizes retry strategies
    """

    def __init__(self, db_path: Path, config: OrchestratorConfig | None = None):
        """
        Initialize the smart orchestrator.

        Args:
            db_path: Path to the SQLite database
            config: Optional orchestrator configuration
        """
        self.db_path = db_path
        self.config = config or OrchestratorConfig()
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        """Get a new database session."""
        return self.SessionLocal()

    def record_attempt(
        self,
        category: str,
        model_id: str,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        duration_ms: int = 0,
        attempt_number: int = 1,
        num_steps: int = 1,
    ) -> None:
        """
        Record a feature implementation attempt for learning.

        Args:
            category: Feature category
            model_id: Model used
            success: Whether the attempt succeeded
            input_tokens: Input token count
            output_tokens: Output token count
            cost: Estimated cost
            duration_ms: Duration in milliseconds
            attempt_number: Which attempt this was (1, 2, 3...)
            num_steps: Number of steps in the feature
        """
        with self._get_session() as session:
            # Update feature pattern
            pattern = session.query(FeaturePattern).filter_by(category=category).first()

            if pattern is None:
                pattern = FeaturePattern(category=category)
                session.add(pattern)

            pattern.total_attempts += 1
            if success:
                pattern.successful_attempts += 1
                # Update average attempts to success (running average)
                if pattern.successful_attempts > 1:
                    pattern.avg_attempts_to_success = (
                        pattern.avg_attempts_to_success * (pattern.successful_attempts - 1) + attempt_number
                    ) / pattern.successful_attempts
                else:
                    pattern.avg_attempts_to_success = attempt_number

            # Update resource averages (running average)
            n = pattern.total_attempts
            pattern.avg_input_tokens = int((pattern.avg_input_tokens * (n - 1) + input_tokens) / n)
            pattern.avg_output_tokens = int((pattern.avg_output_tokens * (n - 1) + output_tokens) / n)
            pattern.avg_cost = (pattern.avg_cost * (n - 1) + cost) / n
            pattern.avg_duration_ms = int((pattern.avg_duration_ms * (n - 1) + duration_ms) / n)
            pattern.avg_steps = (pattern.avg_steps * (n - 1) + num_steps) / n

            # Calculate difficulty based on success rate and attempts needed
            success_rate = pattern.successful_attempts / pattern.total_attempts if pattern.total_attempts > 0 else 0
            pattern.estimated_difficulty = 1.0 - (success_rate * 0.7 + (1.0 / pattern.avg_attempts_to_success) * 0.3)

            # Update model performance
            perf = session.query(ModelPerformance).filter_by(model_id=model_id, category=category).first()

            if perf is None:
                perf = ModelPerformance(model_id=model_id, category=category)
                session.add(perf)

            perf.total_attempts += 1
            if success:
                perf.successful_attempts += 1

            perf.success_rate = perf.successful_attempts / perf.total_attempts
            perf.total_input_tokens += input_tokens
            perf.total_output_tokens += output_tokens
            perf.total_cost += cost
            perf.cost_per_success = perf.total_cost / perf.successful_attempts if perf.successful_attempts > 0 else perf.total_cost
            perf.avg_duration_ms = int((perf.avg_duration_ms * (perf.total_attempts - 1) + duration_ms) / perf.total_attempts)

            # Update best model for category if this model is better
            if perf.total_attempts >= self.config.learning_threshold:
                current_best_rate = pattern.model_success_rate
                if perf.success_rate > current_best_rate:
                    pattern.model_id = model_id
                    pattern.model_success_rate = perf.success_rate

            # Also update overall model performance (no category filter)
            overall_perf = session.query(ModelPerformance).filter_by(model_id=model_id, category=None).first()

            if overall_perf is None:
                overall_perf = ModelPerformance(model_id=model_id, category=None)
                session.add(overall_perf)

            overall_perf.total_attempts += 1
            if success:
                overall_perf.successful_attempts += 1
            overall_perf.success_rate = overall_perf.successful_attempts / overall_perf.total_attempts
            overall_perf.total_cost += cost

            session.commit()

    def get_recommendation(self, category: str, num_steps: int = 1) -> FeatureRecommendation:
        """
        Get a recommendation for implementing a feature.

        Args:
            category: Feature category
            num_steps: Number of steps in the feature

        Returns:
            FeatureRecommendation with model and strategy suggestions
        """
        with self._get_session() as session:
            pattern = session.query(FeaturePattern).filter_by(category=category).first()

            if pattern is None or pattern.total_attempts < self.config.learning_threshold:
                # Not enough data, use defaults
                return FeatureRecommendation(
                    recommended_model=self.config.default_model,
                    expected_attempts=1,
                    estimated_cost=0.0,
                    estimated_duration_ms=0,
                    difficulty=0.5,
                    confidence=0.0,
                    reasoning="Insufficient data for category-specific recommendation",
                )

            # Find best model for this category
            best_perf = (
                session.query(ModelPerformance)
                .filter(
                    ModelPerformance.category == category,
                    ModelPerformance.total_attempts >= self.config.learning_threshold,
                )
                .order_by(
                    # Balance success rate with cost efficiency
                    (ModelPerformance.success_rate * (1 - self.config.cost_weight)
                     - ModelPerformance.cost_per_success * self.config.cost_weight).desc()
                )
                .first()
            )

            recommended_model = best_perf.model_id if best_perf else self.config.default_model
            confidence = min(pattern.total_attempts / 50, 1.0)  # Max confidence at 50 samples

            # Scale estimates based on step count
            step_factor = num_steps / pattern.avg_steps if pattern.avg_steps > 0 else 1.0

            return FeatureRecommendation(
                recommended_model=recommended_model,
                expected_attempts=max(1, round(pattern.avg_attempts_to_success)),
                estimated_cost=pattern.avg_cost * step_factor,
                estimated_duration_ms=int(pattern.avg_duration_ms * step_factor),
                difficulty=pattern.estimated_difficulty,
                confidence=confidence,
                reasoning=f"Based on {pattern.total_attempts} attempts in '{category}' category "
                         f"({pattern.successful_attempts} successful, "
                         f"{round(pattern.successful_attempts/pattern.total_attempts*100, 1)}% success rate)",
            )

    def get_insights(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent learning insights.

        Returns:
            List of insight dictionaries
        """
        with self._get_session() as session:
            insights = (
                session.query(LearningInsight)
                .order_by(LearningInsight.created_at.desc())
                .limit(limit)
                .all()
            )
            return [i.to_dict() for i in insights]

    def generate_insights(self) -> list[LearningInsight]:
        """
        Analyze patterns and generate new insights.

        Returns:
            List of newly generated insights
        """
        new_insights = []

        with self._get_session() as session:
            # Find categories with consistently high failure rates
            struggling_categories = (
                session.query(FeaturePattern)
                .filter(
                    FeaturePattern.total_attempts >= self.config.learning_threshold,
                    FeaturePattern.estimated_difficulty > 0.7,
                )
                .all()
            )

            for pattern in struggling_categories:
                # Check if we already have a recent insight for this
                existing = (
                    session.query(LearningInsight)
                    .filter(
                        LearningInsight.insight_type == "high_difficulty",
                        LearningInsight.category == pattern.category,
                        LearningInsight.created_at > _utc_now() - timedelta(days=7),
                    )
                    .first()
                )

                if not existing:
                    success_rate = pattern.successful_attempts / pattern.total_attempts * 100
                    insight = LearningInsight(
                        insight_type="high_difficulty",
                        category=pattern.category,
                        title=f"High difficulty category: {pattern.category}",
                        description=f"Features in '{pattern.category}' have a {success_rate:.0f}% success rate "
                                   f"and require an average of {pattern.avg_attempts_to_success:.1f} attempts. "
                                   f"Consider breaking down these features into smaller tasks.",
                        confidence=min(pattern.total_attempts / 50, 1.0),
                        data={
                            "successRate": success_rate,
                            "avgAttempts": pattern.avg_attempts_to_success,
                            "totalAttempts": pattern.total_attempts,
                        },
                    )
                    session.add(insight)
                    new_insights.append(insight)

            # Find model efficiency opportunities
            performances = (
                session.query(ModelPerformance)
                .filter(
                    ModelPerformance.category.is_not(None),
                    ModelPerformance.total_attempts >= self.config.learning_threshold,
                )
                .all()
            )

            # Group by category and find if there's a cheaper model with similar success
            category_perfs: dict[str, list[ModelPerformance]] = {}
            for p in performances:
                if p.category not in category_perfs:
                    category_perfs[p.category] = []
                category_perfs[p.category].append(p)

            for category, perfs in category_perfs.items():
                if len(perfs) < 2:
                    continue

                # Sort by cost per success
                sorted_perfs = sorted(perfs, key=lambda x: x.cost_per_success)
                cheapest = sorted_perfs[0]
                most_expensive = sorted_perfs[-1]

                # If cheapest has similar success rate but much lower cost
                if (
                    cheapest.success_rate >= most_expensive.success_rate * 0.9
                    and cheapest.cost_per_success < most_expensive.cost_per_success * 0.5
                ):
                    existing = (
                        session.query(LearningInsight)
                        .filter(
                            LearningInsight.insight_type == "cost_optimization",
                            LearningInsight.category == category,
                            LearningInsight.created_at > _utc_now() - timedelta(days=7),
                        )
                        .first()
                    )

                    if not existing:
                        savings = (most_expensive.cost_per_success - cheapest.cost_per_success) / most_expensive.cost_per_success * 100
                        insight = LearningInsight(
                            insight_type="cost_optimization",
                            category=category,
                            title=f"Cost optimization for {category}",
                            description=f"Using {cheapest.model_id} instead of {most_expensive.model_id} "
                                       f"for '{category}' features could save ~{savings:.0f}% "
                                       f"with similar success rate ({cheapest.success_rate*100:.0f}% vs {most_expensive.success_rate*100:.0f}%).",
                            confidence=min(min(cheapest.total_attempts, most_expensive.total_attempts) / 50, 1.0),
                            data={
                                "cheaperModel": cheapest.model_id,
                                "expensiveModel": most_expensive.model_id,
                                "savingsPercent": savings,
                            },
                        )
                        session.add(insight)
                        new_insights.append(insight)

            session.commit()

        return new_insights

    def get_category_stats(self) -> list[dict[str, Any]]:
        """
        Get statistics for all categories.

        Returns:
            List of category statistics
        """
        with self._get_session() as session:
            patterns = session.query(FeaturePattern).order_by(FeaturePattern.category).all()
            return [p.to_dict() for p in patterns]

    def get_model_stats(self, category: str | None = None) -> list[dict[str, Any]]:
        """
        Get model performance statistics.

        Args:
            category: Optional category filter

        Returns:
            List of model performance stats
        """
        with self._get_session() as session:
            query = session.query(ModelPerformance)

            if category is not None:
                query = query.filter(ModelPerformance.category == category)
            else:
                # Get overall stats (no category)
                query = query.filter(ModelPerformance.category.is_(None))

            performances = query.order_by(ModelPerformance.success_rate.desc()).all()
            return [p.to_dict() for p in performances]


# =============================================================================
# Global Instance
# =============================================================================

_orchestrators: dict[str, SmartOrchestrator] = {}


def get_smart_orchestrator(project_path: Path, config: OrchestratorConfig | None = None) -> SmartOrchestrator:
    """
    Get or create a SmartOrchestrator for a project.

    Args:
        project_path: Path to the project directory
        config: Optional configuration

    Returns:
        SmartOrchestrator instance
    """
    db_path = project_path / ".autocoder" / "learning.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    path_str = str(db_path)
    if path_str not in _orchestrators:
        _orchestrators[path_str] = SmartOrchestrator(db_path, config)

    return _orchestrators[path_str]
