"""
Extracts which columns actually drove the chosen model's predictions, and
explains it in plain language. This did NOT exist before -- model_result
had the model's overall fit quality (R^2), but nothing about which
specific columns mattered to get there. This is what "what things are
affecting the dataset" actually means in data-science terms.

Works for both model families we support:
  - Tree-based (RandomForest, GradientBoosting): uses built-in
    feature_importances_ (how much each feature reduced prediction error
    across all the trees).
  - Linear (LinearRegression, Ridge): uses the absolute value of each
    coefficient as a proxy -- bigger coefficient (on standardized-ish
    one-hot/numeric inputs) means bigger swing in the prediction.

Both are normalized to sum to 1.0 so they're comparable and can be shown
as a simple bar/percentage in the UI, regardless of which model won.
"""

from __future__ import annotations

import numpy as np


def _humanize_feature_name(raw_name: str, categorical_cols: list[str] | None = None) -> str:
    """
    Turns a ColumnTransformer output name like 'cat__account_tier_Enterprise'
    or 'num__signup_month' into 'Account tier (Enterprise)' / 'Signup month'.

    categorical_cols lets us correctly split "account_tier_Enterprise" into
    column="account_tier" + value="Enterprise" instead of naively splitting
    every underscore, which would lose the column/value distinction.
    """
    name = raw_name.split("__", 1)[-1] if "__" in raw_name else raw_name
    categorical_cols = categorical_cols or []

    for col in categorical_cols:
        if name.startswith(col + "_"):
            value = name[len(col) + 1:]
            pretty_col = col.replace("_", " ").capitalize()
            return f"{pretty_col} ({value})"

    return name.replace("_", " ").capitalize()


def get_feature_importance(chosen_model: dict, categorical_cols: list[str] | None = None, top_n: int = 5) -> list[dict]:
    """
    chosen_model is model_result["chosen_model"] from select_and_fit_model()
    -- specifically needs its "pipeline" (fitted Pipeline with "prep" and
    "model" steps). Pass the same categorical_cols used to fit the model so
    one-hot feature names can be split correctly (see _humanize_feature_name).

    Returns a list of {"feature": humanized name, "importance": float 0-1,
    "raw_name": original column name} sorted descending, top_n only.
    Returns [] if the model type doesn't expose anything usable (shouldn't
    happen for our supported model set, but fail safe rather than crash).
    """
    if chosen_model is None:
        return []

    pipeline = chosen_model["pipeline"]
    prep = pipeline.named_steps["prep"]
    model = pipeline.named_steps["model"]

    try:
        feature_names = prep.get_feature_names_out()
    except Exception:
        return []

    if hasattr(model, "feature_importances_"):
        raw_scores = np.asarray(model.feature_importances_)
    elif hasattr(model, "coef_"):
        raw_scores = np.abs(np.asarray(model.coef_)).flatten()
    else:
        return []

    if raw_scores.sum() == 0:
        return []

    normalized = raw_scores / raw_scores.sum()

    ranked = sorted(
        zip(feature_names, normalized),
        key=lambda pair: pair[1],
        reverse=True,
    )[:top_n]

    return [
        {"feature": _humanize_feature_name(name, categorical_cols), "importance": round(float(score), 4), "raw_name": name}
        for name, score in ranked
    ]


def explain_feature_importance(importances: list[dict]) -> str:
    """
    Plain-language summary of the top drivers -- what the educator layer
    actually shows a non-technical user, grounded strictly in the real
    numbers above (never invents which column "should" matter).
    """
    if not importances:
        return "The model didn't expose which columns mattered most for this type of model."

    top = importances[0]
    lines = [f"The single biggest driver was **{top['feature']}**, responsible for about "
             f"{top['importance']*100:.0f}% of what the model paid attention to."]

    if len(importances) > 1:
        rest = ", ".join(f"{i['feature']} ({i['importance']*100:.0f}%)" for i in importances[1:])
        lines.append(f"After that: {rest}.")

    return " ".join(lines)


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

    importances = get_feature_importance(model_result["chosen_model"], categorical_cols=["region", "city", "sales_rep", "account_tier"])
    print("Top features:")
    for i in importances:
        print(f"  {i['feature']}: {i['importance']*100:.1f}%  (raw: {i['raw_name']})")
    print()
    print(explain_feature_importance(importances))
