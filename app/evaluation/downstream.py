"""
Downstream checks: the FINAL acceptance test for the cleaned dataset,
distinct from the per-column stat-checks in loop.py.

Per-column checks (loop.py) answer: "did this specific action improve
this specific column's statistical health?"

Downstream checks (this file) answer: "can the data now actually be USED
for something real?" -- this is what makes the agent's goal genuinely
output-based (Option B from the framework) rather than just "the data
looks cleaner." A column can pass every stat-check individually and the
dataset can still fail here (e.g. wrong dtypes breaking a groupby,
one bad row breaking an aggregation) -- that's the point of having both
layers.

Matplotlib uses the non-interactive "Agg" backend since this runs
headless (no display) -- required or plt.savefig/plt.figure calls will
error out in this environment.
"""

import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, "/home/claude/project")


def check_aggregation(df: pd.DataFrame, group_col: str, value_col: str) -> dict:
    """
    Can we group by a categorical column and aggregate a numeric one,
    getting sane (non-null, non-infinite, non-degenerate) results?
    This is the most common real "downstream task" a learner would want
    to do immediately after cleaning (e.g. "average deal value by region").
    """
    name = f"aggregation({group_col} -> mean({value_col}))"
    try:
        grouped = df.groupby(group_col)[value_col].mean()
    except Exception as e:
        return {"check": name, "passed": False, "reason": f"groupby/aggregation raised: {e}"}

    if grouped.isna().any():
        return {"check": name, "passed": False,
                "reason": f"aggregation produced NaN for group(s): {grouped[grouped.isna()].index.tolist()}"}
    if np.isinf(grouped).any():
        return {"check": name, "passed": False, "reason": "aggregation produced infinite value(s)"}
    if len(grouped) < 2:
        return {"check": name, "passed": False,
                "reason": f"only {len(grouped)} distinct group(s) found -- grouping column likely still messy"}

    return {"check": name, "passed": True,
            "reason": f"clean aggregation across {len(grouped)} groups, values range "
                      f"{grouped.min():.2f} to {grouped.max():.2f}",
            "result_preview": grouped.round(2).to_dict()}


def check_time_series(df: pd.DataFrame, date_col: str, value_col: str) -> dict:
    """
    Can the date column be sorted and used to build a real time trend?
    Verifies the column is genuinely datetime-typed (not string) and that
    sorting + resampling doesn't blow up.
    """
    name = f"time_series(sort {date_col}, trend {value_col})"

    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        return {"check": name, "passed": False,
                "reason": f"{date_col} is not a datetime dtype ({df[date_col].dtype}) -- coercion step didn't run or failed"}

    try:
        ts = df[[date_col, value_col]].dropna().sort_values(date_col)
        monthly = ts.set_index(date_col)[value_col].resample("ME").mean()
    except Exception as e:
        return {"check": name, "passed": False, "reason": f"resampling raised: {e}"}

    if monthly.dropna().shape[0] < 2:
        return {"check": name, "passed": False,
                "reason": "fewer than 2 months of resampled data -- can't show a trend"}

    return {"check": name, "passed": True,
            "reason": f"built a {monthly.dropna().shape[0]}-month trend without error",
            "result_preview": monthly.dropna().round(2).to_dict()}


def check_chart_renders(df: pd.DataFrame, group_col: str, value_col: str) -> dict:
    """
    Actually attempts to render a chart (bar chart of value_col by group_col)
    in-memory. This is deliberately literal -- "can the learner actually
    SEE their data" is the real downstream promise of the product.
    """
    name = f"chart_renders(bar: {group_col} vs {value_col})"
    try:
        grouped = df.groupby(group_col)[value_col].mean()
        fig, ax = plt.subplots()
        grouped.plot(kind="bar", ax=ax)
        ax.set_title(f"{value_col} by {group_col}")
        fig.canvas.draw()  # forces actual rendering, not just object construction
        plt.close(fig)
    except Exception as e:
        return {"check": name, "passed": False, "reason": f"chart rendering raised: {e}"}

    return {"check": name, "passed": True, "reason": "bar chart rendered without error"}


def run_downstream_checks(df: pd.DataFrame, group_col: str, numeric_col: str, date_col: str) -> dict:
    """
    Runs all downstream checks and returns an overall pass/fail plus the
    individual check results -- same log-friendly shape as action_log
    entries, so B/C can consume this identically.
    """
    checks = [
        check_aggregation(df, group_col, numeric_col),
        check_time_series(df, date_col, numeric_col),
        check_chart_renders(df, group_col, numeric_col),
    ]
    overall_passed = all(c["passed"] for c in checks)
    return {"overall_passed": overall_passed, "checks": checks}


if __name__ == "__main__":
    from app.agent.loop import run_agent

    df = pd.read_csv("/mnt/user-data/outputs/messy_sales_dataset.csv")
    cleaned_df, action_log = run_agent(df, verbose=False)

    result = run_downstream_checks(
        cleaned_df, group_col="region", numeric_col="deal_value", date_col="signup_date"
    )

    print(f"Overall downstream check: {'PASSED' if result['overall_passed'] else 'FAILED'}\n")
    for c in result["checks"]:
        status = "PASS" if c["passed"] else "FAIL"
        print(f"[{status}] {c['check']}: {c['reason']}")
        if "result_preview" in c:
            print(f"       preview: {c['result_preview']}")
