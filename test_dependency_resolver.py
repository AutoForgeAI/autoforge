#!/usr/bin/env python3
"""
Dependency Resolver Tests
=========================

Tests for the dependency resolver functions including cycle detection.
Run with: python test_dependency_resolver.py
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from api.dependency_resolver import (
    are_dependencies_satisfied,
    compute_scheduling_scores,
    get_blocked_features,
    get_blocking_dependencies,
    get_ready_features,
    resolve_dependencies,
    would_create_circular_dependency,
)


def test_compute_scheduling_scores_simple_chain():
    """Test scheduling scores for a simple linear dependency chain."""
    print("\nTesting compute_scheduling_scores with simple chain:")

    features = [
        {"id": 1, "priority": 1, "dependencies": []},
        {"id": 2, "priority": 2, "dependencies": [1]},
        {"id": 3, "priority": 3, "dependencies": [2]},
    ]

    scores = compute_scheduling_scores(features)

    # All features should have scores
    passed = True
    for f in features:
        if f["id"] not in scores:
            print(f"  FAIL: Feature {f['id']} missing from scores")
            passed = False

    if passed:
        # Root feature (1) should have highest score (unblocks most)
        if scores[1] > scores[2] > scores[3]:
            print("  PASS: Root feature has highest score, leaf has lowest")
        else:
            print(f"  FAIL: Expected scores[1] > scores[2] > scores[3], got {scores}")
            passed = False

    return passed


def test_compute_scheduling_scores_with_cycle():
    """Test that compute_scheduling_scores handles circular dependencies without hanging."""
    print("\nTesting compute_scheduling_scores with circular dependencies:")

    # Create a cycle: 1 -> 2 -> 3 -> 1
    features = [
        {"id": 1, "priority": 1, "dependencies": [3]},
        {"id": 2, "priority": 2, "dependencies": [1]},
        {"id": 3, "priority": 3, "dependencies": [2]},
    ]

    # Use timeout to detect infinite loop
    def compute_with_timeout():
        return compute_scheduling_scores(features)

    start = time.time()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(compute_with_timeout)
            scores = future.result(timeout=5.0)  # 5 second timeout

        elapsed = time.time() - start

        # Should complete quickly (< 1 second for 3 features)
        if elapsed > 1.0:
            print(f"  FAIL: Took {elapsed:.2f}s (expected < 1s)")
            return False

        # All features should have scores (even cyclic ones)
        if len(scores) == 3:
            print(f"  PASS: Completed in {elapsed:.3f}s with {len(scores)} scores")
            return True
        else:
            print(f"  FAIL: Expected 3 scores, got {len(scores)}")
            return False

    except FuturesTimeoutError:
        print("  FAIL: Infinite loop detected (timed out after 5s)")
        return False


def test_compute_scheduling_scores_self_reference():
    """Test scheduling scores with self-referencing dependency."""
    print("\nTesting compute_scheduling_scores with self-reference:")

    features = [
        {"id": 1, "priority": 1, "dependencies": [1]},  # Self-reference
        {"id": 2, "priority": 2, "dependencies": []},
    ]

    start = time.time()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: compute_scheduling_scores(features))
            scores = future.result(timeout=5.0)

        elapsed = time.time() - start

        if elapsed > 1.0:
            print(f"  FAIL: Took {elapsed:.2f}s (expected < 1s)")
            return False

        if len(scores) == 2:
            print(f"  PASS: Completed in {elapsed:.3f}s with {len(scores)} scores")
            return True
        else:
            print(f"  FAIL: Expected 2 scores, got {len(scores)}")
            return False

    except FuturesTimeoutError:
        print("  FAIL: Infinite loop detected (timed out after 5s)")
        return False


def test_compute_scheduling_scores_complex_cycle():
    """Test scheduling scores with complex circular dependencies."""
    print("\nTesting compute_scheduling_scores with complex cycle:")

    # Features 1-3 form a cycle, feature 4 depends on 1
    features = [
        {"id": 1, "priority": 1, "dependencies": [3]},
        {"id": 2, "priority": 2, "dependencies": [1]},
        {"id": 3, "priority": 3, "dependencies": [2]},
        {"id": 4, "priority": 4, "dependencies": [1]},  # Outside cycle
    ]

    start = time.time()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(lambda: compute_scheduling_scores(features))
            scores = future.result(timeout=5.0)

        elapsed = time.time() - start

        if elapsed > 1.0:
            print(f"  FAIL: Took {elapsed:.2f}s (expected < 1s)")
            return False

        if len(scores) == 4:
            print(f"  PASS: Completed in {elapsed:.3f}s with {len(scores)} scores")
            return True
        else:
            print(f"  FAIL: Expected 4 scores, got {len(scores)}")
            return False

    except FuturesTimeoutError:
        print("  FAIL: Infinite loop detected (timed out after 5s)")
        return False


def test_compute_scheduling_scores_diamond():
    """Test scheduling scores with diamond dependency pattern."""
    print("\nTesting compute_scheduling_scores with diamond pattern:")

    #     1
    #    / \
    #   2   3
    #    \ /
    #     4
    features = [
        {"id": 1, "priority": 1, "dependencies": []},
        {"id": 2, "priority": 2, "dependencies": [1]},
        {"id": 3, "priority": 3, "dependencies": [1]},
        {"id": 4, "priority": 4, "dependencies": [2, 3]},
    ]

    scores = compute_scheduling_scores(features)

    # Feature 1 should have highest score (unblocks 2, 3, and transitively 4)
    if scores[1] > scores[2] and scores[1] > scores[3] and scores[1] > scores[4]:
        # Feature 4 should have lowest score (leaf, unblocks nothing)
        if scores[4] < scores[2] and scores[4] < scores[3]:
            print("  PASS: Root has highest score, leaf has lowest")
            return True
        else:
            print(f"  FAIL: Leaf should have lowest score. Scores: {scores}")
            return False
    else:
        print(f"  FAIL: Root should have highest score. Scores: {scores}")
        return False


def test_compute_scheduling_scores_empty():
    """Test scheduling scores with empty feature list."""
    print("\nTesting compute_scheduling_scores with empty list:")

    scores = compute_scheduling_scores([])

    if scores == {}:
        print("  PASS: Returns empty dict for empty input")
        return True
    else:
        print(f"  FAIL: Expected empty dict, got {scores}")
        return False


def test_would_create_circular_dependency():
    """Test cycle detection for new dependencies."""
    print("\nTesting would_create_circular_dependency:")

    # Current dependencies: 2 depends on 1, 3 depends on 2
    # Dependency chain: 3 -> 2 -> 1 (arrows mean "depends on")
    features = [
        {"id": 1, "priority": 1, "dependencies": []},
        {"id": 2, "priority": 2, "dependencies": [1]},
        {"id": 3, "priority": 3, "dependencies": [2]},
    ]

    passed = True

    # source_id gains dependency on target_id
    # Adding "1 depends on 3" would create cycle: 1 -> 3 -> 2 -> 1
    if would_create_circular_dependency(features, 1, 3):
        print("  PASS: Detected cycle when adding 1 depends on 3")
    else:
        print("  FAIL: Should detect cycle when adding 1 depends on 3")
        passed = False

    # Adding "3 depends on 1" would NOT create cycle (redundant but not circular)
    if not would_create_circular_dependency(features, 3, 1):
        print("  PASS: No false positive for 3 depends on 1")
    else:
        print("  FAIL: False positive for 3 depends on 1")
        passed = False

    # Self-reference should be detected
    if would_create_circular_dependency(features, 1, 1):
        print("  PASS: Detected self-reference")
    else:
        print("  FAIL: Should detect self-reference")
        passed = False

    return passed


def test_resolve_dependencies_with_cycle():
    """Test resolve_dependencies detects and reports cycles."""
    print("\nTesting resolve_dependencies with cycle:")

    # Create a cycle: 1 -> 2 -> 3 -> 1
    features = [
        {"id": 1, "priority": 1, "dependencies": [3]},
        {"id": 2, "priority": 2, "dependencies": [1]},
        {"id": 3, "priority": 3, "dependencies": [2]},
    ]

    result = resolve_dependencies(features)

    # Should report circular dependencies
    if result["circular_dependencies"]:
        print(f"  PASS: Detected cycle: {result['circular_dependencies']}")
        return True
    else:
        print("  FAIL: Should report circular dependencies")
        return False


def test_are_dependencies_satisfied():
    """Test dependency satisfaction checking."""
    print("\nTesting are_dependencies_satisfied:")

    features = [
        {"id": 1, "priority": 1, "dependencies": [], "passes": True},
        {"id": 2, "priority": 2, "dependencies": [1], "passes": False},
        {"id": 3, "priority": 3, "dependencies": [2], "passes": False},
    ]

    passed = True

    # Feature 1 has no deps, should be satisfied
    if are_dependencies_satisfied(features[0], features):
        print("  PASS: Feature 1 (no deps) is satisfied")
    else:
        print("  FAIL: Feature 1 should be satisfied")
        passed = False

    # Feature 2 depends on 1 which passes, should be satisfied
    if are_dependencies_satisfied(features[1], features):
        print("  PASS: Feature 2 (dep on passing) is satisfied")
    else:
        print("  FAIL: Feature 2 should be satisfied")
        passed = False

    # Feature 3 depends on 2 which doesn't pass, should NOT be satisfied
    if not are_dependencies_satisfied(features[2], features):
        print("  PASS: Feature 3 (dep on non-passing) is not satisfied")
    else:
        print("  FAIL: Feature 3 should not be satisfied")
        passed = False

    return passed


def test_get_blocking_dependencies():
    """Test getting blocking dependency IDs."""
    print("\nTesting get_blocking_dependencies:")

    features = [
        {"id": 1, "priority": 1, "dependencies": [], "passes": True},
        {"id": 2, "priority": 2, "dependencies": [], "passes": False},
        {"id": 3, "priority": 3, "dependencies": [1, 2], "passes": False},
    ]

    blocking = get_blocking_dependencies(features[2], features)

    # Only feature 2 should be blocking (1 passes)
    if blocking == [2]:
        print("  PASS: Correctly identified blocking dependency")
        return True
    else:
        print(f"  FAIL: Expected [2], got {blocking}")
        return False


def test_get_ready_features():
    """Test getting ready features."""
    print("\nTesting get_ready_features:")

    features = [
        {"id": 1, "priority": 1, "dependencies": [], "passes": True},
        {"id": 2, "priority": 2, "dependencies": [], "passes": False, "in_progress": False},
        {"id": 3, "priority": 3, "dependencies": [1], "passes": False, "in_progress": False},
        {"id": 4, "priority": 4, "dependencies": [2], "passes": False, "in_progress": False},
    ]

    ready = get_ready_features(features)

    # Features 2 and 3 should be ready
    # Feature 1 passes, feature 4 blocked by 2
    ready_ids = [f["id"] for f in ready]

    if 2 in ready_ids and 3 in ready_ids:
        if 1 not in ready_ids and 4 not in ready_ids:
            print(f"  PASS: Ready features: {ready_ids}")
            return True
        else:
            print(f"  FAIL: Should not include passing/blocked. Got: {ready_ids}")
            return False
    else:
        print(f"  FAIL: Should include 2 and 3. Got: {ready_ids}")
        return False


def test_get_blocked_features():
    """Test getting blocked features."""
    print("\nTesting get_blocked_features:")

    features = [
        {"id": 1, "priority": 1, "dependencies": [], "passes": False},
        {"id": 2, "priority": 2, "dependencies": [1], "passes": False},
    ]

    blocked = get_blocked_features(features)

    # Feature 2 should be blocked by 1
    if len(blocked) == 1 and blocked[0]["id"] == 2:
        if blocked[0]["blocked_by"] == [1]:
            print("  PASS: Correctly identified blocked feature")
            return True
        else:
            print(f"  FAIL: Wrong blocked_by: {blocked[0]['blocked_by']}")
            return False
    else:
        print(f"  FAIL: Expected feature 2 blocked, got: {blocked}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Dependency Resolver Tests")
    print("=" * 60)

    tests = [
        test_compute_scheduling_scores_simple_chain,
        test_compute_scheduling_scores_with_cycle,
        test_compute_scheduling_scores_self_reference,
        test_compute_scheduling_scores_complex_cycle,
        test_compute_scheduling_scores_diamond,
        test_compute_scheduling_scores_empty,
        test_would_create_circular_dependency,
        test_resolve_dependencies_with_cycle,
        test_are_dependencies_satisfied,
        test_get_blocking_dependencies,
        test_get_ready_features,
        test_get_blocked_features,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
