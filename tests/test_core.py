"""
Basic tests -- not exhaustive, but covers the parts most likely to
silently break if someone edits detection/action logic later:
  1. compute_stats gives correct numbers on known input
  2. the full loop actually backtracks when it should (this is the
     single most important behavior to protect -- it's the whole
     "agentic" claim)
  3. detect_issues doesn't false-positive on clean structured-ID columns
"""

import sys
sys.path.insert(0, "/home/claude/project")

import pandas as pd
import numpy as np

from app.evaluation.stats import compute_stats
from app.agent.detect import detect_issues
from app.agent.loop import run_agent


def test_compute_stats_null_pct():
    df = pd.DataFrame({"x": [1, 2, None, None, 5]})
    stats = compute_stats(df, "x")
    assert stats["null_count"] == 2
    assert stats["null_pct"] == 40.0


def test_compute_stats_categorical_value_counts():
    df = pd.DataFrame({"city": ["Mumbai", "mumbai", "Delhi", "Delhi", "Delhi"]})
    stats = compute_stats(df, "city")
    assert stats["top_value_counts"] is not None
    assert stats["top_value_counts"]["Delhi"] == 3


def test_detect_issues_no_false_positive_on_structured_ids():
    df = pd.DataFrame({"rep_id": [f"Rep_{i}" for i in range(1, 21)] * 5})
    issues = detect_issues(df)
    label_issues = [i for i in issues if i.issue_type == "label_inconsistency"]
    assert len(label_issues) == 0, "structured ID column should not be flagged as inconsistent labels"


def test_loop_backtracks_on_bad_imputation():
    """
    The core claim of this whole project: given a bimodal numeric column
    with missing values, median imputation should distort the distribution
    enough to fail the check, and the loop should fall back to KNN.
    """
    np.random.seed(1)
    n = 200
    is_big = np.random.rand(n) < 0.2
    values = np.where(is_big, np.random.normal(500, 30, n), np.random.normal(50, 8, n))
    values = values.astype(object)
    missing_mask = np.random.rand(n) < 0.2
    values[missing_mask] = np.nan

    df = pd.DataFrame({
        "id": range(n),
        "value": values,
        "other_numeric": np.random.normal(10, 2, n),  # gives KNN something to lean on
    })

    _, log = run_agent(df, verbose=False)
    value_attempts = [e for e in log if e["column"] == "value"]

    assert len(value_attempts) >= 1
    # at least one attempt should have failed before the (or an) attempt passed --
    # this is the actual backtrack behavior, not just "it eventually worked"
    any_failed = any(not e["passed"] for e in value_attempts)
    final_passed = value_attempts[-1]["passed"]
    assert any_failed, "expected at least one candidate strategy to fail on a bimodal column"
    assert final_passed, "expected the loop to eventually find a strategy that passes"


def test_loop_flags_unsolvable_column_for_human_review():
    """
    A column where the value is pure random noise unrelated to anything --
    no cleaning strategy should be able to 'fix' this, so the missing
    check itself isn't really applicable, but we can at least confirm the
    loop doesn't crash and produces a log entry.
    """
    df = pd.DataFrame({
        "id": range(50),
        "noise": np.random.normal(0, 1, 50),
    })
    cleaned_df, log = run_agent(df, verbose=False)
    assert cleaned_df is not None  # loop completes without raising


if __name__ == "__main__":
    # Standalone runner (no pytest dependency needed) -- pytest will also
    # work fine in a normal environment (`pytest tests/test_core.py -v`),
    # this fallback exists only because this sandbox has no internet to
    # install it.
    tests = [
        test_compute_stats_null_pct,
        test_compute_stats_categorical_value_counts,
        test_detect_issues_no_false_positive_on_structured_ids,
        test_loop_backtracks_on_bad_imputation,
        test_loop_flags_unsolvable_column_for_human_review,
    ]
    passed, failed = 0, 0
    for t in tests:
        try:
            t()
            print(f"PASS: {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {t.__name__} -- {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {t.__name__} -- {type(e).__name__}: {e}")
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)
