"""
The agent loop: observe -> decide -> act -> evaluate -> adapt.
"""

import pandas as pd
from app.evaluation.stats import compute_stats
from app.agent.detect import detect_issues
from app.actions.actions import (
    impute_median, impute_knn, impute_mode,
    normalize_categories, coerce_numeric_strings, coerce_dates,
)

DECISION_TREE = {
    "missing_numeric": [
        ("impute_median", impute_median, "the typical middle value is the simplest fix, so we try it first", "can distort data with distinct groups"),
        ("impute_knn", impute_knn, "similar rows can make smarter guesses when groups exist", "needs related columns and is slower"),
    ],
    "missing_categorical": [
        ("impute_mode", impute_mode, "the most common category is usually a safe first guess", "can be wrong for genuinely rare categories"),
    ],
    "label_inconsistency": [
        ("normalize_categories", normalize_categories, "matching similar spellings is the standard fix", "may miss totally different aliases"),
    ],
    "format_error_numeric": [
        ("coerce_numeric_strings", coerce_numeric_strings, "numbers stored as text must be converted before math", "unexpected text formats can slip through"),
    ],
    "format_error_date": [
        ("coerce_dates", coerce_dates, "mixed date formats need one consistent representation", "ambiguous dates can occasionally be misread"),
    ],
}

NUMERIC_SKEW_SHIFT_MAX_PCT = 15.0

def _passes_check(issue_type: str, before_stats: dict, after_stats: dict) -> tuple[bool, str]:
    if after_stats["null_pct"] > 0 and issue_type.startswith("missing"):
        return False, f"still has {after_stats['null_pct']}% nulls after imputation"

    if issue_type == "missing_numeric":
        before_skew, after_skew = before_stats["skew"], after_stats["skew"]
        if before_skew is None or after_skew is None or before_skew == 0:
            return True, "no meaningful skew to compare, accepting"
        shift_pct = abs(after_skew - before_skew) / abs(before_skew) * 100
        if shift_pct > NUMERIC_SKEW_SHIFT_MAX_PCT:
            return False, f"skew shifted {shift_pct:.1f}% ({before_skew} -> {after_skew}), exceeds {NUMERIC_SKEW_SHIFT_MAX_PCT}% threshold -- distribution distorted"
        return True, f"skew shift {shift_pct:.1f}%, within {NUMERIC_SKEW_SHIFT_MAX_PCT}% threshold"

    if issue_type == "label_inconsistency":
        if after_stats["unique_count"] >= before_stats["unique_count"]:
            return False, "unique count didn't decrease -- normalization had no effect"
        return True, f"unique labels reduced {before_stats['unique_count']} -> {after_stats['unique_count']}"

    if issue_type == "format_error_numeric":
        return (after_stats["skew"] is not None, "column now parses as numeric" if after_stats["skew"] is not None else "column still doesn't parse as numeric after coercion")

    if issue_type == "format_error_date":
        return (after_stats["null_pct"] <= 5.0, "dates parsed consistently" if after_stats["null_pct"] <= 5.0 else f"{after_stats['null_pct']}% of dates failed to parse after coercion")

    return True, "no specific check defined, accepting by default"

def run_agent(df: pd.DataFrame, verbose: bool = True) -> tuple[pd.DataFrame, list[dict]]:
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
        last_after_stats = before_stats
        for candidate_name, candidate_fn, why_tried, tradeoff in candidates:
            trial_df = candidate_fn(working_df, column)
            after_stats = compute_stats(trial_df, column)
            last_after_stats = after_stats
            passed, reason = _passes_check(issue.issue_type, before_stats, after_stats)
            action_log.append({
                "column": column, "issue_type": issue.issue_type,
                "action_tried": candidate_name, "why_tried": why_tried,
                "tradeoff": tradeoff, "before_stats": before_stats,
                "after_stats": after_stats, "passed": passed, "reason": reason,
            })
            if verbose:
                print(f"  -> tried {candidate_name}: {'PASSED' if passed else 'FAILED (backtracking)'} -- {reason}")
            if passed:
                working_df = trial_df
                resolved = True
                break

        if not resolved:
            action_log.append({
                "column": column, "issue_type": issue.issue_type,
                "action_tried": "flag_for_human_review",
                "why_tried": "every strategy we know for this kind of problem was tried",
                "tradeoff": "", "before_stats": before_stats,
                "after_stats": last_after_stats, "passed": False,
                "reason": "all candidate strategies exhausted, needs human review",
            })
            if verbose:
                print(f"  -> ALL candidates failed for {column}. Flagging for human review.")
    return working_df, action_log

def get_all_options_considered(issue_type: str, tried_names: list[str] | None = None) -> list[dict]:
    tried_names = tried_names or []
    return [{"name": name, "why_tried": why, "tradeoff": tradeoff, "was_tried": name in tried_names}
            for name, _fn, why, tradeoff in DECISION_TREE.get(issue_type, [])]
