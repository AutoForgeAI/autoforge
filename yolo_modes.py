"""
YOLO Mode Configuration
=======================

Defines different YOLO mode variants for the autonomous coding system.

YOLO Modes:
- standard: Full testing mode (no YOLO)
- yolo: Pure YOLO - skip all testing, lint/type-check only
- yolo_review: YOLO with periodic code reviews
- yolo_parallel: Multiple YOLO agents on independent features
- yolo_staged: YOLO for early phases, full testing for later phases
"""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class YoloMode(Enum):
    """Available YOLO mode variants."""

    STANDARD = "standard"  # Full testing mode
    YOLO = "yolo"  # Pure YOLO - skip testing
    YOLO_REVIEW = "yolo_review"  # YOLO with periodic reviews
    YOLO_PARALLEL = "yolo_parallel"  # Multiple parallel agents
    YOLO_STAGED = "yolo_staged"  # YOLO early, test late


@dataclass
class YoloModeConfig:
    """Configuration for a YOLO mode variant."""

    mode: YoloMode
    skip_browser_testing: bool
    skip_regression: bool
    enable_review: bool
    review_frequency: int  # Review every N features
    enable_parallel: bool
    max_parallel_agents: int
    staged_yolo_threshold: float  # Phase percentage to switch from YOLO to standard

    @property
    def prompt_name(self) -> str:
        """Get the prompt template name for this mode."""
        if self.mode == YoloMode.STANDARD:
            return "coding_prompt"
        elif self.mode == YoloMode.YOLO:
            return "coding_prompt_yolo"
        elif self.mode == YoloMode.YOLO_REVIEW:
            return "coding_prompt_yolo_review"
        elif self.mode == YoloMode.YOLO_PARALLEL:
            return "coding_prompt_yolo"  # Uses same prompt, different execution
        elif self.mode == YoloMode.YOLO_STAGED:
            return "coding_prompt_yolo"  # Dynamically switches
        return "coding_prompt"

    @property
    def description(self) -> str:
        """Get a human-readable description."""
        descriptions = {
            YoloMode.STANDARD: "Full testing mode with browser verification",
            YoloMode.YOLO: "Skip testing for rapid prototyping",
            YoloMode.YOLO_REVIEW: "Skip testing but add periodic code reviews",
            YoloMode.YOLO_PARALLEL: "Multiple YOLO agents on independent features",
            YoloMode.YOLO_STAGED: "YOLO for early phases, testing for late phases",
        }
        return descriptions.get(self.mode, "Unknown mode")

    @property
    def icon(self) -> str:
        """Get an icon for the mode."""
        icons = {
            YoloMode.STANDARD: "shield",
            YoloMode.YOLO: "zap",
            YoloMode.YOLO_REVIEW: "zap-eye",
            YoloMode.YOLO_PARALLEL: "zap-parallel",
            YoloMode.YOLO_STAGED: "trending-up",
        }
        return icons.get(self.mode, "circle")


# Predefined configurations for each mode
YOLO_MODE_CONFIGS = {
    YoloMode.STANDARD: YoloModeConfig(
        mode=YoloMode.STANDARD,
        skip_browser_testing=False,
        skip_regression=False,
        enable_review=False,
        review_frequency=0,
        enable_parallel=False,
        max_parallel_agents=1,
        staged_yolo_threshold=0.0,
    ),
    YoloMode.YOLO: YoloModeConfig(
        mode=YoloMode.YOLO,
        skip_browser_testing=True,
        skip_regression=True,
        enable_review=False,
        review_frequency=0,
        enable_parallel=False,
        max_parallel_agents=1,
        staged_yolo_threshold=0.0,
    ),
    YoloMode.YOLO_REVIEW: YoloModeConfig(
        mode=YoloMode.YOLO_REVIEW,
        skip_browser_testing=True,
        skip_regression=True,
        enable_review=True,
        review_frequency=5,  # Review every 5 features
        enable_parallel=False,
        max_parallel_agents=1,
        staged_yolo_threshold=0.0,
    ),
    YoloMode.YOLO_PARALLEL: YoloModeConfig(
        mode=YoloMode.YOLO_PARALLEL,
        skip_browser_testing=True,
        skip_regression=True,
        enable_review=False,
        review_frequency=0,
        enable_parallel=True,
        max_parallel_agents=3,
        staged_yolo_threshold=0.0,
    ),
    YoloMode.YOLO_STAGED: YoloModeConfig(
        mode=YoloMode.YOLO_STAGED,
        skip_browser_testing=True,  # Initially
        skip_regression=True,  # Initially
        enable_review=False,
        review_frequency=0,
        enable_parallel=False,
        max_parallel_agents=1,
        staged_yolo_threshold=0.75,  # Switch at 75% completion
    ),
}


def get_yolo_config(mode: YoloMode | str) -> YoloModeConfig:
    """Get the configuration for a YOLO mode.

    Args:
        mode: YoloMode enum or string name

    Returns:
        YoloModeConfig for the mode
    """
    if isinstance(mode, str):
        mode = YoloMode(mode)
    return YOLO_MODE_CONFIGS.get(mode, YOLO_MODE_CONFIGS[YoloMode.STANDARD])


def get_effective_mode_for_phase(
    mode: YoloMode,
    phase_order: int,
    total_phases: int,
) -> YoloMode:
    """Get the effective mode considering staged YOLO.

    For YOLO_STAGED mode, this determines whether to use YOLO or standard
    based on the current phase position.

    Args:
        mode: The configured YOLO mode
        phase_order: Current phase order (0-indexed)
        total_phases: Total number of phases

    Returns:
        Effective YoloMode to use
    """
    if mode != YoloMode.YOLO_STAGED:
        return mode

    config = get_yolo_config(mode)

    if total_phases == 0:
        return YoloMode.YOLO

    # Calculate phase progress
    phase_percentage = (phase_order + 1) / total_phases

    if phase_percentage >= config.staged_yolo_threshold:
        # Late phase - use standard mode
        return YoloMode.STANDARD
    else:
        # Early phase - use YOLO
        return YoloMode.YOLO


def should_trigger_review(
    mode: YoloMode,
    unreviewed_count: int,
) -> bool:
    """Check if a review cycle should be triggered.

    Args:
        mode: Current YOLO mode
        unreviewed_count: Number of unreviewed completed tasks

    Returns:
        True if review should be triggered
    """
    config = get_yolo_config(mode)

    if not config.enable_review:
        return False

    return unreviewed_count >= config.review_frequency


def get_prompt_for_yolo_mode(
    mode: YoloMode | str,
    project_dir: Optional[Path] = None,
    phase_order: int = 0,
    total_phases: int = 1,
) -> str:
    """Get the prompt content for a YOLO mode.

    Args:
        mode: YOLO mode to use
        project_dir: Optional project directory for custom prompts
        phase_order: Current phase order (for staged mode)
        total_phases: Total phases (for staged mode)

    Returns:
        Prompt content as string
    """
    from prompts import load_prompt

    if isinstance(mode, str):
        mode = YoloMode(mode)

    # Get effective mode for staged YOLO
    effective_mode = get_effective_mode_for_phase(mode, phase_order, total_phases)
    config = get_yolo_config(effective_mode)

    return load_prompt(config.prompt_name, project_dir)


def get_available_modes() -> list[dict]:
    """Get list of available YOLO modes for UI display.

    Returns:
        List of mode information dictionaries
    """
    return [
        {
            "value": mode.value,
            "label": mode.name.replace("_", " ").title(),
            "description": config.description,
            "icon": config.icon,
            "skip_testing": config.skip_browser_testing,
            "has_review": config.enable_review,
            "parallel": config.enable_parallel,
        }
        for mode, config in YOLO_MODE_CONFIGS.items()
    ]
