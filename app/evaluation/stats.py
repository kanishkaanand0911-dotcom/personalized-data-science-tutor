"""
compute_stats: the single function every decision in the agent depends on.
"""

import pandas as pd

def compute_stats(df: pd.DataFrame, column: str) -> dict:
    series = df[column]
    n = len(series)
    null_count = series.isna().sum()
    stats = {
        "column": column, "dtype": str(series.dtype), "n_rows": n,
        "null_count": int(null_count),
        "null_pct": round(null_count / n * 100, 2) if n else 0.0,
        "unique_count": int(series.nunique(dropna=True)),
        "skew": None, "mean": None, "std": None,
        "top_value_counts": None,
        "sample_values": series.dropna().sample(min(5, series.dropna().shape[0]), random_state=1).tolist()
            if series.dropna().shape[0] > 0 else [],
    }
    numeric_series = pd.to_numeric(series, errors="coerce")
    non_null = series.dropna()
    convertible_frac = numeric_series.dropna().shape[0] / len(non_null) if len(non_null) else 0
    if convertible_frac > 0.9 and numeric_series.dropna().shape[0] >= 3:
        clean_numeric = numeric_series.dropna()
        stats["skew"] = round(float(clean_numeric.skew()), 3)
        stats["mean"] = round(float(clean_numeric.mean()), 2)
        stats["std"] = round(float(clean_numeric.std()), 2)

    is_text = pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)
    if is_text:
        stats["top_value_counts"] = series.value_counts().head(10).to_dict()
    return stats
