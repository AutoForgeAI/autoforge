"""
Backlog and Spec Roadmapping
============================

Shared helpers for the Backlog state and maturity tags (alpha / limited beta /
beta) used by the REST API, the MCP server and the parallel orchestrator.

- Backlog features are "not committed / not ready" and are never handed to
  the coding agents. A human promotes them to Pending once the ready checks
  pass (or explicitly overrides the checks).
- Maturity tags influence scheduling: among build-ready features, the
  orchestrator picks tags in the configured order first (default
  beta > limited_beta > alpha), then falls back to the dependency-aware
  scheduling score. Untagged features sort after all tagged ones.
"""

from typing import Any, Callable

MATURITY_LEVELS: tuple[str, ...] = ("alpha", "limited_beta", "beta")
MATURITY_LABELS: dict[str, str] = {
    "alpha": "Alpha",
    "limited_beta": "Limited Beta",
    "beta": "Beta",
}
DEFAULT_MATURITY_ORDER: tuple[str, ...] = ("beta", "limited_beta", "alpha")

# Global settings key (registry) holding the comma-separated maturity order
MATURITY_ORDER_SETTING = "maturity_order"


def normalize_maturity(value: str | None) -> str | None:
    """Normalize a maturity tag ("Limited Beta", "limited-beta" -> "limited_beta").

    Returns None for empty values. Raises ValueError for unknown tags.
    """
    if value is None:
        return None
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None
    if normalized not in MATURITY_LEVELS:
        raise ValueError(f"Invalid maturity tag '{value}'. Must be one of: {', '.join(MATURITY_LEVELS)}")
    return normalized


def parse_maturity_order(value: str | None) -> list[str]:
    """Parse a comma-separated maturity order, falling back to the default.

    Unknown or duplicate entries are dropped; missing levels are appended in
    default order so every tag always has a rank.
    """
    order: list[str] = []
    for part in (value or "").split(","):
        try:
            tag = normalize_maturity(part)
        except ValueError:
            continue
        if tag and tag not in order:
            order.append(tag)
    if not order:
        return list(DEFAULT_MATURITY_ORDER)
    for tag in DEFAULT_MATURITY_ORDER:
        if tag not in order:
            order.append(tag)
    return order


def get_configured_maturity_order() -> list[str]:
    """Read the maturity order from global settings (registry)."""
    try:
        from registry import get_setting
        return parse_maturity_order(get_setting(MATURITY_ORDER_SETTING))
    except Exception:
        return list(DEFAULT_MATURITY_ORDER)


def maturity_rank(maturity: str | None, order: list[str] | tuple[str, ...]) -> int:
    """Rank of a maturity tag (lower = scheduled first). Untagged sorts last."""
    if maturity is not None and maturity in order:
        return list(order).index(maturity)
    return len(order)


def ready_sort_key(
    scores: dict[int, float],
    order: list[str] | tuple[str, ...] = DEFAULT_MATURITY_ORDER,
) -> Callable[[dict[str, Any]], tuple]:
    """Sort key for build-ready features.

    Maturity rank first (configured order, untagged last), then the
    dependency-aware scheduling score (higher first), then priority, then id.
    """
    def key(f: dict[str, Any]) -> tuple:
        return (
            maturity_rank(f.get("maturity"), order),
            -scores.get(f["id"], 0),
            f.get("priority", 999),
            f["id"],
        )
    return key


def is_backlog(feature: dict[str, Any]) -> bool:
    """True when a feature dict is in the Backlog state."""
    return bool(feature.get("backlog"))


def compute_readiness(feature: dict[str, Any], features_by_id: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Evaluate the "ready" checks gating promotion from Backlog to Pending.

    Args:
        feature: Feature dict (as produced by Feature.to_dict()).
        features_by_id: All features keyed by id, used to validate dependencies.

    Returns:
        List of {"id", "label", "passed", "detail"} dicts.
    """
    description = (feature.get("description") or "").strip()
    steps = [s for s in (feature.get("steps") or []) if isinstance(s, str) and s.strip()]
    deps = feature.get("dependencies") or []
    missing_deps = [d for d in deps if d not in features_by_id]
    backlog_deps = [d for d in deps if d in features_by_id and is_backlog(features_by_id[d])]

    checks = [
        {
            "id": "description",
            "label": "Requirements described",
            "passed": len(description) >= 20,
            "detail": None if len(description) >= 20 else "Description must be at least 20 characters",
        },
        {
            "id": "acceptance_criteria",
            "label": "Acceptance criteria / test steps defined",
            "passed": len(steps) > 0,
            "detail": None if steps else "Add at least one test step",
        },
        {
            "id": "maturity",
            "label": "Spec reviewed (maturity tag assigned)",
            "passed": bool(feature.get("maturity")),
            "detail": None if feature.get("maturity") else "Assign alpha, limited beta or beta",
        },
        {
            "id": "dependencies",
            "label": "Dependencies committed (none in Backlog)",
            "passed": not missing_deps and not backlog_deps,
            "detail": (
                f"Missing dependencies: {missing_deps}" if missing_deps
                else f"Dependencies still in Backlog: {backlog_deps}" if backlog_deps
                else None
            ),
        },
    ]
    return checks


def failed_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only the checks that did not pass."""
    return [c for c in checks if not c["passed"]]
