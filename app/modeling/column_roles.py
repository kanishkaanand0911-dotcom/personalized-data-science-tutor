"""
Auto-detects feature roles from a cleaned dataframe + a user-chosen target
column -- this is what makes the pipeline work on ANY uploaded dataset,
not just the demo CSV with its hardcoded column list.

Without this, every new dataset would need someone to manually type out
which columns are numeric vs categorical vs "ignore this, it's an ID" --
exactly the kind of thing a real user uploading their own data can't be
expected to do.
"""

from __future__ import annotations

import re
import pandas as pd

ID_LIKE_PATTERN = re.compile(r"(^id$|_id$|^id_|^record_id$|^index$)", re.IGNORECASE)
HIGH_CARDINALITY_TEXT_RATIO = 0.5  # if >50% of rows have a unique value, treat as free text/ID, not a category


def auto_detect_feature_roles(df: pd.DataFrame, target_col: str) -> dict:
    """
    Returns {"feature_cols": [...], "numeric_cols": [...], "categorical_cols": [...]}.

    Rules, in order:
    - target_col itself is never a feature
    - obvious ID-like columns (by name pattern) are excluded
    - datetime columns are excluded as direct features (the model_selector
      caller is expected to derive a numeric feature from them first, e.g.
      signup_month, the same way the demo script already does)
    - free-text / very-high-cardinality text columns are excluded (not
      useful as categorical features, and one-hot encoding them would
      blow up the feature space)
    - remaining numeric columns -> numeric_cols
    - remaining text columns -> categorical_cols
    """
    feature_cols, numeric_cols, categorical_cols = [], [], []

    for col in df.columns:
        if col == target_col:
            continue
        if ID_LIKE_PATTERN.search(col):
            continue
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue  # caller should derive a numeric feature (month, day-of-week, etc.) before calling this

        is_text = pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])
        if is_text:
            cardinality_ratio = df[col].nunique(dropna=True) / len(df) if len(df) else 1
            if cardinality_ratio > HIGH_CARDINALITY_TEXT_RATIO:
                continue  # looks like free text or an ID, not a usable category
            categorical_cols.append(col)
            feature_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
            feature_cols.append(col)
        # other dtypes (e.g. bool) are silently skipped for now -- rare in
        # real uploaded CSVs and not worth the complexity yet

    return {"feature_cols": feature_cols, "numeric_cols": numeric_cols, "categorical_cols": categorical_cols}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/home/claude/project")
    from app.agent.loop import run_agent

    df = pd.read_csv("/home/claude/project/data/messy_sales_dataset.csv")
    cleaned_df, _ = run_agent(df, verbose=False)
    cleaned_df["signup_month"] = cleaned_df["signup_date"].dt.month
    cleaned_df = cleaned_df.drop(columns=["signup_date"])  # already extracted the useful numeric piece

    roles = auto_detect_feature_roles(cleaned_df, target_col="deal_value")
    print("Auto-detected roles for target='deal_value':")
    for k, v in roles.items():
        print(f"  {k}: {v}")
