"""
Real chart rendering with matplotlib.

The agent layer decides WHICH chart and explains WHY; this module actually
draws it. Charts are written to PNG files rather than shown, because the
platform runs headless and the API returns a path a frontend can serve.

The "Agg" backend is set before pyplot is imported -- required in a headless
environment or every savefig call raises.
"""

from __future__ import annotations

import os
import uuid

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.core.config import settings

MAX_CATEGORIES = 12   # beyond this a bar chart is unreadable; we show the top N


def _new_path(prefix: str) -> str:
    os.makedirs(settings.chart_dir, exist_ok=True)
    return os.path.join(settings.chart_dir, f"{prefix}_{uuid.uuid4().hex[:8]}.png")


def _finish(fig, ax, title: str, xlabel: str, ylabel: str, prefix: str) -> str:
    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    path = _new_path(prefix)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return path


def bar_chart(df: pd.DataFrame, category_col: str, value_col: str, agg: str = "mean") -> dict:
    grouped = getattr(df.groupby(category_col)[value_col], agg)().sort_values(ascending=False)
    truncated = len(grouped) > MAX_CATEGORIES
    grouped = grouped.head(MAX_CATEGORIES)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(grouped.index.astype(str), grouped.values, color="#4C78A8")
    ax.tick_params(axis="x", rotation=45 if grouped.index.astype(str).str.len().max() > 6 else 0)
    path = _finish(fig, ax, f"{agg.title()} {value_col} by {category_col}",
                   category_col, f"{agg} of {value_col}", "bar")

    return {"chart_type": "bar", "path": path, "columns": [category_col, value_col],
            "data": grouped.round(2).to_dict(), "truncated": truncated}


def line_chart(df: pd.DataFrame, date_col: str, value_col: str, freq: str = "ME") -> dict:
    ts = df[[date_col, value_col]].dropna().sort_values(date_col)
    series = ts.set_index(date_col)[value_col].resample(freq).mean().dropna()

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(series.index, series.values, marker="o", color="#F58518")
    fig.autofmt_xdate()
    path = _finish(fig, ax, f"{value_col} over time", date_col, value_col, "line")

    return {"chart_type": "line", "path": path, "columns": [date_col, value_col],
            "data": {str(k.date()): round(float(v), 2) for k, v in series.items()},
            "n_periods": len(series)}


def histogram(df: pd.DataFrame, value_col: str, bins: int = 20) -> dict:
    values = df[value_col].dropna()

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(values, bins=bins, color="#54A24B", edgecolor="white")
    path = _finish(fig, ax, f"Distribution of {value_col}", value_col, "How many records", "hist")

    return {"chart_type": "histogram", "path": path, "columns": [value_col],
            "data": {"mean": round(float(values.mean()), 2),
                     "median": round(float(values.median()), 2),
                     "min": round(float(values.min()), 2),
                     "max": round(float(values.max()), 2),
                     "skew": round(float(values.skew()), 2)}}


def scatter_plot(df: pd.DataFrame, x_col: str, y_col: str) -> dict:
    pair = df[[x_col, y_col]].dropna()

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.scatter(pair[x_col], pair[y_col], alpha=0.6, color="#E45756", s=18)
    path = _finish(fig, ax, f"{y_col} vs {x_col}", x_col, y_col, "scatter")

    corr = pair[x_col].corr(pair[y_col])
    return {"chart_type": "scatter", "path": path, "columns": [x_col, y_col],
            "data": {"correlation": round(float(corr), 3) if pd.notna(corr) else None,
                     "n_points": len(pair)}}


RENDERERS = {"bar": bar_chart, "line": line_chart, "histogram": histogram, "scatter": scatter_plot}


def render(chart_type: str, df: pd.DataFrame, x: str, y: str | None = None) -> dict:
    """
    Dispatch to the right renderer. Returns {"error": ...} rather than raising,
    so one unchartable column never breaks a lesson.
    """
    if chart_type not in RENDERERS:
        return {"error": f"unsupported chart type '{chart_type}'"}
    try:
        if chart_type == "histogram":
            return histogram(df, x)
        if chart_type == "bar":
            return bar_chart(df, x, y)
        if chart_type == "line":
            return line_chart(df, x, y)
        return scatter_plot(df, x, y)
    except Exception as e:  # noqa: BLE001
        return {"error": f"could not render {chart_type}: {e}"}
