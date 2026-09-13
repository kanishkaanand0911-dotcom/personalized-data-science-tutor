"""
The agent loop: ties detection -> decision tree -> action -> evaluation ->
backtrack together. This is the actual "observe -> decide -> act -> evaluate
-> adapt" behavior the hackathon requires.
"""

import sys
import pandas as pd

sys.path.insert(0, "/home/claude/project")
from app.evaluation.stats import compute_stats
from app.agent.detect import detect_issues
from app.actions.actions import (
    impute_median, impute_knn, impute_mode,
    normalize_categories,
    coerce_numeric_strings, coerce_dates,
)

# ---- Decision tree: issue_type -> ordered list of (name, function) candidates ----
DECISION_TREE = {
    "missing_numeric": [
        ("impute_median", impute_median),
        ("impute_knn", impute_knn),
    ],
    "missing_categorical": [
        ("impute_mode", impute_mode),
    ],
    "label_inconsistency": [
        ("normalize_categories", normalize_categories),
    ],
    "format_error_numeric": [
        ("coerce_numeric_strings", coerce_numeric_strings),
    ],
    "format_error_date": [
        ("coerce_dates", coerce_dates),
    ],
}

# ---- Acceptance thresholds per issue type ----
# These decide pass/fail after an action. Calibrated against the real
# dataset (see console output from actions.py test run):
#   - median imputation on deal_value: skew shift ~21% -> should FAIL
#   - KNN imputation on deal_value:    skew shift ~7.6% -> should PASS
# so a 15% relative-skew-shift threshold cleanly separates them.
NUMERIC_SKEW_SHIFT_MAX_PCT = 15.0


def _passes_check(issue_type: str, before_stats: dict, after_stats: dict) -> tuple[bool, str]:
    """Returns (passed, reason_string) -- the reason is what gets narrated/logged."""

    # Universal check: the action must not have reintroduced/left nulls
    if after_stats["null_pct"] > 0 and issue_type.startswith("missing"):
        return False, f"still has {after_stats['null_pct']}% nulls after imputation"

    if issue_type == "missing_numeric":
        before_skew = before_stats["skew"]
        after_skew = after_stats["skew"]
        if before_skew is None or after_skew is None or before_skew == 0:
            return True, "no meaningful skew to compare, accepting"
        shift_pct = abs(after_skew - before_skew) / abs(before_skew) * 100
        if shift_pct > NUMERIC_SKEW_SHIFT_MAX_PCT:
            return False, (
                f"skew shifted {shift_pct:.1f}% ({before_skew} -> {after_skew}), "
                f"exceeds {NUMERIC_SKEW_SHIFT_MAX_PCT}% threshold -- distribution distorted"
            )
        return True, f"skew shift {shift_pct:.1f}%, within {NUMERIC_SKEW_SHIFT_MAX_PCT}% threshold"

    if issue_type == "label_inconsistency":
        # success = raw label count actually dropped toward a small canonical set
        if after_stats["unique_count"] >= before_stats["unique_count"]:
            return False, "unique count didn't decrease -- normalization had no effect"
        return True, f"unique labels reduced {before_stats['unique_count']} -> {after_stats['unique_count']}"

    if issue_type in ("format_error_numeric",):
        # success = column is now genuinely numeric (skew becomes computable)
        if after_stats["skew"] is None:
            return False, "column still doesn't parse as numeric after coercion"
        return True, "column now parses as numeric"

    if issue_type == "format_error_date":
        if after_stats["null_pct"] > 5.0:
            return False, f"{after_stats['null_pct']}% of dates failed to parse after coercion"
        return True, "dates parsed consistently"

    # default: accept if we got this far
    return True, "no specific check defined, accepting by default"


def run_agent(df: pd.DataFrame, verbose: bool = True) -> tuple[pd.DataFrame, list[dict]]:
    """
    Returns (cleaned_df, action_log). action_log is a list of dicts, one
    per attempt (including failed/backtracked attempts) -- this full log,
    not just the final result, is what proves agentic behavior in the demo.
    """
    working_df = df.copy()
    action_log = []

    issues = detect_issues(working_df)
    if verbose:
        print(f"[detect] found {len(issues)} issues\n")

    for issue in issues:
        column = issue.column
        candidates = DECISION_TREE.get(issue.issue_type, [])
        before_stats = compute_stats(working_df, column)

        if verbose:
            print(f"[issue] {column}: {issue.issue_type} (severity={issue.severity})")

        resolved = False
        last_after_stats = before_stats  # if candidates is empty entirely, fall back to before_stats
        for candidate_name, candidate_fn in candidates:
            trial_df = candidate_fn(working_df, column)
            after_stats = compute_stats(trial_df, column)
            last_after_stats = after_stats
            passed, reason = _passes_check(issue.issue_type, before_stats, after_stats)

            entry = {
                "column": column,
                "issue_type": issue.issue_type,
                "action_tried": candidate_name,
                "before_stats": before_stats,
                "after_stats": after_stats,
                "passed": passed,
                "reason": reason,
            }
            action_log.append(entry)

            if verbose:
                status = "PASSED" if passed else "FAILED (backtracking)"
                print(f"  -> tried {candidate_name}: {status} -- {reason}")

            if passed:
                working_df = trial_df   # commit the change
                resolved = True
                break
            # else: trial_df is discarded, working_df unchanged, loop tries next candidate

        if not resolved:
            if verbose:
                print(f"  -> ALL candidates failed for {column}. Flagging for human review.")
            action_log.append({
                "column": column,
                "issue_type": issue.issue_type,
                "action_tried": "flag_for_human_review",  # matches B's narration schema convention
                "before_stats": before_stats,
                "after_stats": last_after_stats,
                "passed": False,
                "reason": "all candidate strategies exhausted, needs human review",
            })

        if verbose:
            print()

    return working_df, action_log


if __name__ == "__main__":
    df = pd.read_csv("/mnt/user-data/outputs/messy_sales_dataset.csv")
    cleaned_df, log = run_agent(df)

    print("=" * 60)
    print(f"Done. {len(log)} total actions logged.")
    print("\nFinal cleaned dataset sample:")
    print(cleaned_df.head(5).to_string())
    print("\nRemaining nulls per column:")
    print(cleaned_df.isna().sum())
