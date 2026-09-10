"""
Exploratory Data Analysis -- runs BEFORE cleaning even starts, so the user
sees what a data scientist actually looks at first: distributions,
correlations, outliers. This was completely missing before -- the agent
went straight from "here's messy data" to "here's what I fixed" with no
"here's what I noticed" step in between.

Returns a case-shaped dict (same structure as lesson_builder's cases) so
it slots into the same rendering pattern Person C already knows how to
display.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def _detect_outliers_iqr(series: pd.Series) -> int:
    """Standard IQR method: count points outside 1.5x the interquartile range."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((series < lower) | (series > upper)).sum())


def explore_dataset(df: pd.DataFrame, target_col: str | None = None) -> dict:
    """
    Returns a summary of the RAW (pre-cleaning) dataset:
      - shape (rows/columns)
      - per-numeric-column: mean, outlier count
      - strongest correlation pair among numeric columns (if 2+ exist)
      - target column's distribution shape, if target_col is given
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    column_summaries = []
    for col in numeric_cols:
        clean_series = df[col].dropna()
        if len(clean_series) < 3:
            continue
        column_summaries.append({
            "column": col,
            "mean": round(float(clean_series.mean()), 2),
            "outlier_count": _detect_outliers_iqr(clean_series),
            "outlier_pct": round(_detect_outliers_iqr(clean_series) / len(clean_series) * 100, 1),
        })

    strongest_corr = None
    if len(numeric_cols) >= 2:
        corr_matrix = df[numeric_cols].corr().abs()
        # pandas 3.0's copy-on-write makes .values read-only by default;
        # to_numpy(copy=True) forces a genuinely writable array
        corr_array = corr_matrix.to_numpy(copy=True)
        np.fill_diagonal(corr_array, 0)
        max_flat_idx = np.argmax(corr_array)
        i, j = np.unravel_index(max_flat_idx, corr_array.shape)
        max_val = corr_array[i, j]
        if max_val > 0:
            strongest_corr = {"col_a": numeric_cols[i], "col_b": numeric_cols[j], "correlation": round(float(max_val), 3)}

    target_distribution = None
    if target_col and target_col in numeric_cols:
        clean_target = df[target_col].dropna()
        if len(clean_target) >= 3:
            skew = float(clean_target.skew())
            target_distribution = {
                "column": target_col,
                "skew": round(skew, 2),
                "shape": "right-skewed (a few large values pull the average up)" if skew > 1
                         else "left-skewed (a few small values pull the average down)" if skew < -1
                         else "roughly balanced (no strong skew)",
            }

    return {
        "id": "__eda__",
        "kind": "eda",
        "concept": "Exploring your data",
        "title": "The case of the first look",
        "n_rows": len(df),
        "n_cols": len(df.columns),
        "column_summaries": column_summaries,
        "strongest_correlation": strongest_corr,
        "target_distribution": target_distribution,
    }


def explain_eda(eda: dict) -> str:
    """Plain-language summary, grounded strictly in the numbers already computed above."""
    lines = [f"This dataset has {eda['n_rows']} rows and {eda['n_cols']} columns."]

    high_outlier_cols = [c for c in eda["column_summaries"] if c["outlier_pct"] > 5]
    if high_outlier_cols:
        worst = max(high_outlier_cols, key=lambda c: c["outlier_pct"])
        lines.append(f"The '{worst['column']}' column has some unusually extreme values -- "
                      f"about {worst['outlier_pct']}% of its rows look like outliers.")

    if eda["strongest_correlation"]:
        sc = eda["strongest_correlation"]
        if sc["correlation"] > 0.7:
            lines.append(f"'{sc['col_a']}' and '{sc['col_b']}' are strongly related to each other "
                          f"(correlation of {sc['correlation']}).")
        elif sc["correlation"] > 0.3:
            lines.append(f"'{sc['col_a']}' and '{sc['col_b']}' show a modest relationship "
                          f"(correlation of {sc['correlation']}) -- worth a look, but not a strong pattern.")
        else:
            lines.append("No two columns showed a meaningful relationship with each other -- "
                          "the strongest pairing was still very weak.")

    if eda["target_distribution"]:
        td = eda["target_distribution"]
        lines.append(f"The column we're trying to understand, '{td['column']}', is {td['shape']}.")

    return " ".join(lines)


if __name__ == "__main__":
    df = pd.read_csv("/home/claude/project/data/messy_sales_dataset.csv")
    eda = explore_dataset(df, target_col="deal_value")
    print(f"Rows: {eda['n_rows']}, Columns: {eda['n_cols']}\n")
    for c in eda["column_summaries"]:
        print(f"  {c['column']}: mean={c['mean']}, outliers={c['outlier_count']} ({c['outlier_pct']}%)")
    print(f"\nStrongest correlation: {eda['strongest_correlation']}")
    print(f"Target distribution: {eda['target_distribution']}")
    print(f"\nPlain language: {explain_eda(eda)}")
