"""
Groups A's raw per-attempt action_log/model_log into teachable "cases" --
one case per column (or one case for model selection), with every attempt
in order. This is what turns a flat attempt log into something a lesson
UI can actually present one concept at a time.

Fully dynamic -- built from whatever detect_issues() actually finds on
the user's real uploaded data, not hardcoded to any specific dataset or
column set. This is the one thing the earlier HTML prototype did NOT do
(it hardcoded the 5 demo columns) -- fixed here for the real backend.
"""

from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.agent.loop import get_all_options_considered

CONCEPT_BY_ISSUE_TYPE = {
    "missing_numeric": "Handling missing data",
    "missing_categorical": "Handling missing data",
    "label_inconsistency": "Fixing inconsistent labels",
    "format_error_numeric": "Standardizing formats",
    "format_error_date": "Standardizing formats",
}

TITLE_TEMPLATE_BY_ISSUE_TYPE = {
    "missing_numeric": "The case of the missing {col} entries",
    "missing_categorical": "The case of the missing {col} entries",
    "label_inconsistency": "The case of the many-named {col}",
    "format_error_numeric": "The case of the {col} hiding as text",
    "format_error_date": "The case of the mismatched {col}",
}


def _humanize_column(column: str) -> str:
    return column.replace("_", " ")


def _build_cleaning_case(column: str, entries: list[dict]) -> dict:
    issue_type = entries[0]["issue_type"]
    concept = CONCEPT_BY_ISSUE_TYPE.get(issue_type, "Cleaning your data")
    title_template = TITLE_TEMPLATE_BY_ISSUE_TYPE.get(issue_type, "The case of the '{col}' column")
    title = title_template.format(col=_humanize_column(column))

    attempts = [
        {
            "action_tried": e["action_tried"],
            "why_tried": e.get("why_tried", ""),
            "tradeoff": e.get("tradeoff", ""),
            "result": e["reason"],
            "passed": e["passed"],
        }
        for e in entries
    ]

    tried_names = [e["action_tried"] for e in entries]
    options_considered = get_all_options_considered(issue_type, tried_names)

    return {
        "id": column,
        "kind": "cleaning",
        "concept": concept,
        "title": title,
        "attempts": attempts,
        "options_considered": options_considered,  # NEW: full pros/cons, including untried options
        "resolved": entries[-1]["passed"],
        "had_retry": len(entries) > 1,
    }


def _build_model_case(model_log: list[dict], all_candidates_considered: list[dict] | None = None) -> dict:
    attempts = [
        {
            "action_tried": e["model_tried"],
            "why_tried": e.get("why_tried", ""),
            "tradeoff": e.get("tradeoff", ""),
            "result": e["reason"],
            "passed": e["passed"],
        }
        for e in model_log
    ]
    return {
        "id": "__model__",
        "kind": "model",
        "concept": "Choosing a model",
        "title": "The case of picking the right model",
        "attempts": attempts,
        "options_considered": all_candidates_considered or [],  # NEW
        "resolved": model_log[-1]["passed"] if model_log else False,
        "had_retry": len(model_log) > 1,
    }


def build_cases(action_log: list[dict], model_log: list[dict] | None = None,
                 all_candidates_considered: list[dict] | None = None) -> list[dict]:
    """
    Returns an ordered list of case dicts, one per column (grouping all of
    that column's attempts together, in the order they occurred) plus one
    final case for model selection if model_log is given.
    """
    by_column: dict[str, list[dict]] = {}
    for entry in action_log:
        by_column.setdefault(entry["column"], []).append(entry)

    cases = [_build_cleaning_case(col, entries) for col, entries in by_column.items()]

    if model_log:
        cases.append(_build_model_case(model_log, all_candidates_considered))

    return cases


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/claude/project")
    import pandas as pd
    from app.agent.loop import run_agent
    from app.modeling.model_selector import select_and_fit_model

    df = pd.read_csv("/home/claude/project/data/messy_sales_dataset.csv")
    cleaned_df, action_log = run_agent(df, verbose=False)
    cleaned_df["signup_month"] = cleaned_df["signup_date"].dt.month
    model_result = select_and_fit_model(
        cleaned_df, target_col="deal_value",
        feature_cols=["region", "city", "sales_rep", "signup_month", "account_tier"],
        numeric_cols=["signup_month"],
        categorical_cols=["region", "city", "sales_rep", "account_tier"],
    )

    cases = build_cases(action_log, model_result["model_log"])
    for c in cases:
        print(f"\n[{c['concept']}] {c['title']} (resolved={c['resolved']}, retry={c['had_retry']})")
        for a in c["attempts"]:
            status = "PASS" if a["passed"] else "FAIL"
            print(f"  {status} tried {a['action_tried']} because {a['why_tried']}")
            print(f"       -> {a['result']}")
