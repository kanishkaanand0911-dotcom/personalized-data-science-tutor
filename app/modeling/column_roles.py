"""
Auto-detects feature roles from a cleaned dataframe + a user-chosen target
column -- this is what makes the pipeline work on ANY uploaded dataset.
"""

from __future__ import annotations
import re
import pandas as pd

ID_LIKE_PATTERN = re.compile(r"(^id$|_id$|^id_|^record_id$|^index$)", re.IGNORECASE)
HIGH_CARDINALITY_TEXT_RATIO = 0.5

def auto_detect_feature_roles(df: pd.DataFrame, target_col: str) -> dict:
    """Returns feature, numeric and categorical columns automatically."""
    feature_cols, numeric_cols, categorical_cols = [], [], []

    for col in df.columns:
        if col == target_col or ID_LIKE_PATTERN.search(col):
            continue
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            continue

        is_text = pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])
        if is_text:
            cardinality_ratio = df[col].nunique(dropna=True) / len(df) if len(df) else 1
            if cardinality_ratio > HIGH_CARDINALITY_TEXT_RATIO:
                continue
            categorical_cols.append(col)
            feature_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
            feature_cols.append(col)

    return {
        "feature_cols": feature_cols,
        "numeric_cols": numeric_cols,
        "categorical_cols": categorical_cols,
    }
