"""
Extracts which columns actually drove the chosen model's predictions and
explains the result in plain language.
"""

from __future__ import annotations
import numpy as np

def _humanize_feature_name(raw_name: str, categorical_cols: list[str] | None = None) -> str:
    name = raw_name.split("__", 1)[-1] if "__" in raw_name else raw_name
    categorical_cols = categorical_cols or []
    for col in categorical_cols:
        if name.startswith(col + "_"):
            value = name[len(col) + 1:]
            return f"{col.replace('_', ' ').capitalize()} ({value})"
    return name.replace("_", " ").capitalize()

def get_feature_importance(chosen_model: dict, categorical_cols: list[str] | None = None, top_n: int = 5) -> list[dict]:
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
    ranked = sorted(zip(feature_names, normalized), key=lambda pair: pair[1], reverse=True)[:top_n]

    return [
        {
            "feature": _humanize_feature_name(name, categorical_cols),
            "importance": round(float(score), 4),
            "raw_name": name,
        }
        for name, score in ranked
    ]

def explain_feature_importance(importances: list[dict]) -> str:
    if not importances:
        return "The model didn't expose which columns mattered most for this type of model."

    top = importances[0]
    lines = [
        f"The single biggest driver was **{top['feature']}**, responsible for about "
        f"{top['importance']*100:.0f}% of what the model paid attention to."
    ]

    if len(importances) > 1:
        rest = ", ".join(f"{i['feature']} ({i['importance']*100:.0f}%)" for i in importances[1:])
        lines.append(f"After that: {rest}.")
    return " ".join(lines)
