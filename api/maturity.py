"""
Backlog, Maturity Tags and Ready Checks
=======================================

Shared helpers for the backlog / iterative spec roadmapping workflow:

- ``backlog`` features are "not committed / not ready" and are never handed
  to agents until a human promotes them to Pending.
- Every feature can carry a maturity tag (alpha / limited_beta / beta) that
  is assigned during spec review. Among build-ready features, the agent queue
  is ordered by maturity first (configurable, default beta > limited_beta >
  alpha), then by the existing dependency-aware scheduling score.
- ``check_readiness`` implements the "spec completeness" checklist that gates
  promotion from Backlog to Pending.
"""

from typing import Any, Iterable

MATURITY_LEVELS: tuple[str, ...] = ("alpha", "limited_beta", "beta")
DEFAULT_MATURITY_ORDER: tuple[str, ...] = ("beta", "limited_beta", "alpha")

# Registry settings key holding the comma-separated maturity priority order
MATURITY_ORDER_SETTING = "maturity_priority"


def parse_maturity_order(value: str | Iterable[str] | None) -> list[str]:
    """Normalize a maturity order into a complete list of known levels.

    Unknown entries and duplicates are dropped; any level missing from the
    input is appended in default order so every level always has a rank.
    """
    if value is None:
        return list(DEFAULT_MATURITY_ORDER)
    items = value.split(",") if isinstance(value, str) else list(value)
    order: list[str] = []
    for item in items:
        level = str(item).strip().lower().replace(" ", "_").replace("-", "_")
        if level in MATURITY_LEVELS and level not in order:
            order.append(level)
    for level in DEFAULT_MATURITY_ORDER:
        if level not in order:
            order.append(level)
    return order


def get_maturity_order() -> list[str]:
    """Read the configured maturity order from global settings (with fallback)."""
    try:
        from registry import get_setting
        return parse_maturity_order(get_setting(MATURITY_ORDER_SETTING))
    except Exception:
        return list(DEFAULT_MATURITY_ORDER)


def maturity_rank(feature: dict, order: list[str]) -> int:
    """Sort rank for a feature's maturity tag (lower = scheduled first).

    Untagged features rank after every tagged feature, so tagging work during
    spec review always moves it ahead of unreviewed work. When nothing is
    tagged, all features share the same rank and ordering is unchanged.
    """
    maturity = feature.get("maturity")
    if maturity in order:
        return order.index(maturity)
    return len(order)


def is_schedulable(feature: dict) -> bool:
    """True when a feature may be handed to a coding agent (ignoring dependencies)."""
    return not (
        feature.get("passes")
        or feature.get("in_progress")
        or feature.get("needs_human_input")
        or feature.get("backlog")
    )


def check_readiness(feature: dict, all_features: list[dict]) -> list[dict[str, Any]]:
    """Run the spec completeness checklist for promoting a feature to Pending.

    Returns a list of ``{"id", "label", "passed"}`` items. A feature is ready
    when every item passed.
    """
    feature_map = {f["id"]: f for f in all_features}
    deps = [d for d in (feature.get("dependencies") or []) if isinstance(d, int)]
    steps = feature.get("steps") or []

    missing_deps = [d for d in deps if d not in feature_map or d == feature["id"]]
    backlog_deps = [d for d in deps if d in feature_map and feature_map[d].get("backlog")]

    return [
        {
            "id": "description",
            "label": "Description is filled in",
            "passed": bool((feature.get("description") or "").strip()),
        },
        {
            "id": "acceptance_criteria",
            "label": "At least one acceptance/test step is defined",
            "passed": any(isinstance(s, str) and s.strip() for s in steps),
        },
        {
            "id": "maturity",
            "label": "Maturity tag assigned during spec review",
            "passed": feature.get("maturity") in MATURITY_LEVELS,
        },
        {
            "id": "dependencies_exist",
            "label": "All dependencies exist" + (f" (missing: {missing_deps})" if missing_deps else ""),
            "passed": not missing_deps,
        },
        {
            "id": "dependencies_committed",
            "label": "No dependency is still in Backlog" + (f" (backlog: {backlog_deps})" if backlog_deps else ""),
            "passed": not backlog_deps,
        },
    ]


def sort_build_queue(
    features: list[dict],
    scheduling_scores: dict[int, float],
    maturity_order: list[str] | None = None,
) -> None:
    """Sort build-ready features in place for the agent queue.

    Order: maturity tag rank, then dependency-aware scheduling score (higher
    first), then user priority, then id.
    """
    order = maturity_order if maturity_order is not None else list(DEFAULT_MATURITY_ORDER)
    features.sort(key=lambda f: (
        maturity_rank(f, order),
        -scheduling_scores.get(f["id"], 0),
        f.get("priority", 999),
        f["id"],
    ))
