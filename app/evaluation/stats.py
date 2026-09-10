"""
compute_stats: the single function every decision in the agent depends on.

Called BEFORE an action (to know what we're dealing with) and AFTER an
action (to check whether the action actually helped). Comparing the two
dicts is how the agent evaluates its own work.
"""

import pandas as pd
import numpy as np


def compute_stats(df: pd.DataFrame, column: str) -> dict:
    """
    Return a snapshot of a column's health.

    Numeric-specific keys (skew) are only meaningful for numeric columns;
    categorical-specific keys (top_value_counts) only for object columns.
    We compute what's relevant and set the rest to None, rather than
    guessing — the caller decides what to compare based on issue type.
    """
    series = df[column]
    n = len(series)
    null_count = series.isna().sum()

    stats = {
        "column": column,
        "dtype": str(series.dtype),
        "n_rows": n,
        "null_count": int(null_count),
        "null_pct": round(null_count / n * 100, 2) if n else 0.0,
        "unique_count": int(series.nunique(dropna=True)),
        "skew": None,
        "mean": None,
        "std": None,
        "top_value_counts": None,
        "sample_values": series.dropna().sample(
            min(5, series.dropna().shape[0]), random_state=1
        ).tolist() if series.dropna().shape[0] > 0 else [],
    }

    # Numeric-specific stats
    numeric_series = pd.to_numeric(series, errors="coerce")
    # Only treat as "numeric" if most non-null values actually converted
    non_null = series.dropna()
    if len(non_null) > 0:
        convertible_frac = numeric_series.dropna().shape[0] / len(non_null)
    else:
        convertible_frac = 0

    if convertible_frac > 0.9 and numeric_series.dropna().shape[0] >= 3:
        clean_numeric = numeric_series.dropna()
        stats["skew"] = round(float(clean_numeric.skew()), 3)
        stats["mean"] = round(float(clean_numeric.mean()), 2)
        stats["std"] = round(float(clean_numeric.std()), 2)

    # Categorical-specific stats
    # NOTE: pandas >=3.0 gives CSV-loaded string columns a native "str" dtype
    # instead of the old "object" dtype, so `series.dtype == object` silently
    # breaks on newer pandas. is_string_dtype/is_object_dtype together cover
    # both old and new pandas.
    is_text = pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)
    if is_text:
        stats["top_value_counts"] = series.value_counts().head(10).to_dict()

    return stats


if __name__ == "__main__":
    # Quick standalone test against the real dataset
    df = pd.read_csv("/mnt/user-data/outputs/messy_sales_dataset.csv")

    for col in ["deal_value", "city", "signup_date", "revenue_display", "region"]:
        print(f"\n--- {col} ---")
        s = compute_stats(df, col)
        for k, v in s.items():
            print(f"  {k}: {v}")
