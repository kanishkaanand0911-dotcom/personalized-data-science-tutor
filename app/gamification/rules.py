"""
Pure XP/badge rules -- no state, no persistence, no UI. Person C's
frontend owns actual state (XP totals, streaks, which badges a user has
already seen) -- these functions just answer "how much XP does this
event earn" and "does this case qualify for a badge", given the case
data A already produces. Keeping this stateless and side-effect-free
means it's trivially testable and trivially portable into whatever
frontend C builds (Streamlit, a notebook, anything).
"""

from __future__ import annotations

XP_RULES = {
    "case_viewed": 15,
    "quiz_correct_first_try": 20,
    "quiz_correct_after_retry": 5,
}


def badge_for_case(case: dict) -> str | None:
    """
    Returns a badge name if this case's content qualifies for one, or
    None. A case can only earn one badge (the first matching rule wins) --
    the UI is responsible for not re-awarding a badge the user already has.
    """
    if not case["resolved"]:
        return None
    if case["kind"] == "model":
        return "Model Scout"
    if case["had_retry"]:
        return "Detective's Eye"
    if case["concept"] == "Standardizing formats":
        return "Format Fixer"
    return None


def final_badge(cases: list[dict]) -> str | None:
    """Awarded once every case in the run is resolved."""
    if cases and all(c["resolved"] for c in cases):
        return "Case Closed"
    return None


if __name__ == "__main__":
    # Quick sanity check against real case shapes
    import sys
    sys.path.insert(0, "/home/claude/project")
    sys.path.insert(0, "/home/claude/project/app/educator")
    import pandas as pd
    from app.agent.loop import run_agent
    from app.modeling.model_selector import select_and_fit_model
    from lesson_builder import build_cases

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
    total_xp = 0
    for c in cases:
        badge = badge_for_case(c)
        total_xp += XP_RULES["case_viewed"] + XP_RULES["quiz_correct_first_try"]
        print(f"{c['title']}: badge={badge}")
    print(f"\nfinal_badge = {final_badge(cases)}")
    print(f"total_xp (all first-try correct) = {total_xp}")
