"""Sequences the existing backend into one run and shapes the output for the
screens. All decisions still come from app/; this module only calls it and
reformats.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from app.agent.detect import detect_issues
from app.agent.loop import DECISION_TREE, run_agent
from app.evaluation.downstream import (
    check_aggregation,
    check_chart_renders,
    check_time_series,
)
from app.modeling.model_selector import select_and_fit_model

from web.copy import (
    CHECK_LABELS,
    ISSUE_TITLES,
    MODEL_EXPLANATIONS,
    MODEL_LABELS,
    STRATEGY_LABELS,
    analogy_for,
    plain,
    plain_reason,
)

MAX_ROWS = 20000
MAX_COLS = 60


# ---------------------------------------------------------------- dataset load


def load_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw))
    if df.shape[1] < 2:
        raise ValueError("This file needs at least two columns to work with.")
    if len(df) < 10:
        raise ValueError("This file needs at least ten rows to work with.")
    if len(df) > MAX_ROWS or df.shape[1] > MAX_COLS:
        raise ValueError(
            f"This file is larger than the demo supports "
            f"(limit {MAX_ROWS} rows and {MAX_COLS} columns)."
        )
    return df


def dataset_summary(df: pd.DataFrame, name: str) -> dict:
    missing = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()}
    preview = df.head(6).astype(object).where(pd.notna(df.head(6)), None)
    return {
        "name": name,
        "rows": int(len(df)),
        "cols": int(df.shape[1]),
        "columns": list(df.columns),
        "preview": preview.to_dict(orient="records"),
        "missing": missing,
    }


# ------------------------------------------------------------------- levels


def build_levels(df: pd.DataFrame, role: str | None) -> list[dict]:
    """One level per detected issue, in detection order. Carries the candidate
    strategies for the guess, but no outcome."""
    levels = []
    for idx, issue in enumerate(detect_issues(df)):
        candidates = DECISION_TREE.get(issue.issue_type, [])
        options = _guess_options(issue.issue_type, candidates)
        levels.append(
            {
                "id": idx,
                "column": issue.column,
                "issue_type": issue.issue_type,
                "severity": issue.severity,
                "title": ISSUE_TITLES.get(issue.issue_type, issue.issue_type),
                "analogy": analogy_for(issue.issue_type, role),
                "question": options["question"],
                "options": options["options"],
                "guess_kind": options["kind"],
            }
        )
    return levels


def _guess_options(issue_type: str, candidates: list) -> dict:
    if len(candidates) > 1:
        opts = []
        for name, _fn in candidates:
            meta = STRATEGY_LABELS.get(name, {"name": name, "blurb": ""})
            opts.append({"id": name, "label": meta["name"], "blurb": meta["blurb"]})
        return {
            "kind": "which_strategy",
            "question": "Which fix do you think the agent will keep?",
            "options": opts,
        }

    only = candidates[0][0] if candidates else "flag_for_human_review"
    meta = STRATEGY_LABELS.get(only, {"name": only, "blurb": ""})
    return {
        "kind": "pass_fail",
        "question": f"The agent will try “{meta['name']}” first. Does it hold up?",
        "options": [
            {"id": "pass", "label": "It passes the check", "blurb": meta["blurb"]},
            {
                "id": "fail",
                "label": "It fails and the agent backtracks",
                "blurb": "The fix distorts the column enough to be rejected.",
            },
        ],
    }


# --------------------------------------------------------- full deterministic run


@dataclass
class PipelineRun:
    cleaned_df: pd.DataFrame
    action_log: list[dict]
    downstream: dict
    model: dict
    lesson: str
    columns_changed: list[str] = field(default_factory=list)


def run_pipeline(df: pd.DataFrame) -> PipelineRun:
    cleaned_df, action_log = run_agent(df, verbose=False)
    changed = _changed_columns(df, cleaned_df)
    downstream = _run_downstream(cleaned_df)
    model = _run_model(cleaned_df, df)
    lesson = _lesson(action_log, model.get("raw_model_log", []))
    return PipelineRun(
        cleaned_df=cleaned_df,
        action_log=action_log,
        downstream=downstream,
        model=model,
        lesson=lesson,
        columns_changed=changed,
    )


def _changed_columns(before: pd.DataFrame, after: pd.DataFrame) -> list[str]:
    changed = []
    for c in before.columns:
        if c not in after.columns:
            continue
        b, a = before[c], after[c]
        if str(b.dtype) != str(a.dtype) or b.isna().sum() != a.isna().sum():
            changed.append(c)
            continue
        try:
            if not b.fillna("\x00").astype(str).equals(a.fillna("\x00").astype(str)):
                changed.append(c)
        except Exception:
            changed.append(c)
    return changed


# ------------------------------------------------------------- level reveal


def level_reveal(run: PipelineRun, level: dict) -> dict:
    """The agent's real attempts for this column, plus whether the learner's
    guess matched. The guess is scored here and nowhere else."""
    column = level["column"]
    attempts_raw = [e for e in run.action_log if e["column"] == column]
    attempts = [_shape_attempt(e) for e in attempts_raw]

    kept = next((e for e in attempts_raw if e["passed"]), None)
    agent_choice = kept["action_tried"] if kept else "flag_for_human_review"
    first_passed = bool(attempts_raw and attempts_raw[0]["passed"])

    return {
        "attempts": attempts,
        "agent_choice": agent_choice,
        "agent_choice_label": STRATEGY_LABELS.get(agent_choice, {}).get("name", agent_choice),
        "first_passed": first_passed,
        "resolved": kept is not None,
    }


def _shape_attempt(entry: dict) -> dict:
    meta = STRATEGY_LABELS.get(entry["action_tried"], {"name": entry["action_tried"]})
    return {
        "strategy": entry["action_tried"],
        "label": meta["name"],
        "passed": bool(entry["passed"]),
        "reason": plain_reason(entry["reason"]),
        "before": _stat_line(entry.get("before_stats", {})),
        "after": _stat_line(entry.get("after_stats", {})),
    }


def _stat_line(stats: dict) -> dict:
    return {
        "null_pct": stats.get("null_pct"),
        "skew": stats.get("skew"),
        "unique_count": stats.get("unique_count"),
        "dtype": stats.get("dtype"),
    }


# A right guess is worth more than the passive read bonus; a wrong one costs
# points rather than just withholding them, so the score reflects real
# understanding, not just showing up.
GUESS_CORRECT_POINTS = 15
GUESS_WRONG_POINTS = -8
READ_BONUS_POINTS = 5


def score_guess(level: dict, reveal: dict, choice_id: str) -> dict:
    if level["guess_kind"] == "which_strategy":
        correct = choice_id == reveal["agent_choice"]
    else:
        want_pass = choice_id == "pass"
        correct = want_pass == reveal["first_passed"]
    return {"correct": correct, "points": GUESS_CORRECT_POINTS if correct else GUESS_WRONG_POINTS}


# --------------------------------------------------------------- level quiz

# A recap, not a second guess: worth less than a guess either way, in
# points and in penalty - it still counts, just more lightly.
QUIZ_CORRECT_POINTS = 5
QUIZ_WRONG_POINTS = -3


def build_quiz(level: dict, reveal: dict) -> list[dict]:
    """Two quick multiple-choice questions grounded in this level's real,
    already-revealed outcome. Deterministic in (level, reveal), so the same
    questions and options come back whether this is called to render the quiz
    or to grade it - nothing about the quiz needs to be stored in the session."""
    questions = [
        {
            "id": "issue",
            "prompt": f"What kind of problem was in the “{level['column']}” column?",
            "options": _issue_options(level["title"]),
            "answer": level["title"],
        }
    ]

    attempt_labels = [a["label"] for a in reveal["attempts"]]
    if reveal["resolved"] and len(set(attempt_labels)) > 1:
        questions.append(
            {
                "id": "fix",
                "prompt": f"Which fix did the agent actually keep for “{level['column']}”?",
                "options": sorted(set(attempt_labels)),
                "answer": reveal["agent_choice_label"],
            }
        )
    else:
        yes, no = "Yes, it passed the check", "No, it needed another approach"
        questions.append(
            {
                "id": "first_try",
                "prompt": f"Did the agent's first fix for “{level['column']}” pass its check?",
                "options": [yes, no],
                "answer": yes if reveal["first_passed"] else no,
            }
        )

    return questions


def _issue_options(correct: str) -> list[str]:
    pool = sorted(set(ISSUE_TITLES.values()) | {correct})
    others = [o for o in pool if o != correct][:3]
    return sorted(others + [correct])


def build_model_quiz(model: dict) -> list[dict]:
    """The modeling phase's own version of build_quiz() - same shape, same
    scoring, grounded in the real model step's outcome instead of a level's.
    A learner can skip modeling entirely (see /api/model/quiz's caller), so
    this only needs to run once per session, not once per model attempt."""
    if not model.get("available") or not model.get("chosen"):
        no_model = "No model passed its accuracy check, so it was flagged for a human"
        return [
            {
                "id": "model_outcome",
                "prompt": "What happened when the agent tried to build a model on your data?",
                "options": sorted([no_model, "A model was successfully chosen and kept"]),
                "answer": no_model,
            }
        ]

    chosen_label = model["chosen"]["label"]
    pool = sorted(set(MODEL_LABELS.values()) | {chosen_label})
    others = [o for o in pool if o != chosen_label][:3]
    model_options = sorted(others + [chosen_label])

    yes, no = (
        "Yes - it explained the pattern well and passed its check",
        "No - it was rejected and the agent tried something else",
    )
    return [
        {
            "id": "model_chosen",
            "prompt": "Which model did the agent end up choosing for your data?",
            "options": model_options,
            "answer": chosen_label,
        },
        {
            "id": "model_fit",
            "prompt": "Was the model the agent kept considered a good fit?",
            "options": [yes, no],
            "answer": yes,
        },
    ]


def score_quiz(questions: list[dict], answers: dict[str, str]) -> dict:
    """Only grades questions the learner actually answered - a flashcard
    only ever submits one of a level's two real questions, and the other
    one was never shown, so it must not be silently scored as wrong."""
    lookup = {q["id"]: q["answer"] for q in questions}
    results = {qid: (answers.get(qid) == correct) for qid, correct in lookup.items() if qid in answers}
    points = sum(QUIZ_CORRECT_POINTS if ok else QUIZ_WRONG_POINTS for ok in results.values())
    return {"results": results, "points": points}


# ------------------------------------------------------------ downstream checks


def _run_downstream(df: pd.DataFrame) -> dict:
    group_col = _pick_group_col(df)
    numeric_col = _pick_numeric_col(df)
    date_col = _pick_date_col(df)

    checks = []
    if group_col and numeric_col:
        checks.append(("aggregation", check_aggregation(df, group_col, numeric_col)))
        checks.append(("chart_renders", check_chart_renders(df, group_col, numeric_col)))
    if date_col and numeric_col:
        checks.append(("time_series", check_time_series(df, date_col, numeric_col)))

    shaped = []
    for key, result in checks:
        shaped.append(
            {
                "key": key,
                "label": CHECK_LABELS.get(key, key),
                "passed": bool(result["passed"]),
                "reason": plain(result["reason"]),
                "preview": _small_preview(result.get("result_preview")),
            }
        )
    overall = bool(shaped) and all(c["passed"] for c in shaped)
    return {
        "overall_passed": overall,
        "checks": shaped,
        "columns_used": {"group": group_col, "value": numeric_col, "date": date_col},
    }


# --------------------------------------------------------------- visualization


def visualization_data(cleaned_df: pd.DataFrame) -> dict:
    """Real chart-ready data from the agent's own cleaned output - a
    histogram per numeric column, a bar count per low-cardinality text
    column, and a month-over-month trend if a date column exists. Same
    column-picking helpers as the downstream checks, so "the chart" and
    "the check" always agree on which columns matter."""
    numeric_cols = [
        c for c in cleaned_df.columns
        if pd.api.types.is_numeric_dtype(cleaned_df[c]) and not _looks_like_id(cleaned_df, c)
    ]
    categorical_cols = [
        c for c in cleaned_df.columns
        if (pd.api.types.is_string_dtype(cleaned_df[c]) or pd.api.types.is_object_dtype(cleaned_df[c]))
        and 2 <= cleaned_df[c].nunique(dropna=True) <= 15
    ]

    numeric_charts = []
    for col in numeric_cols[:3]:
        series = cleaned_df[col].dropna()
        if series.empty or series.nunique() < 2:
            continue
        counts, edges = np.histogram(series, bins=8)
        bars = [
            {"label": f"{edges[i]:.0f}–{edges[i + 1]:.0f}", "value": int(counts[i])}
            for i in range(len(counts))
        ]
        numeric_charts.append({"column": col, "bars": bars})

    category_charts = []
    for col in categorical_cols[:3]:
        counts = cleaned_df[col].value_counts().head(10)
        bars = [{"label": str(k), "value": int(v)} for k, v in counts.items()]
        category_charts.append({"column": col, "bars": bars})

    trend_chart = None
    date_col = _pick_date_col(cleaned_df)
    numeric_col = _pick_numeric_col(cleaned_df)
    if date_col and numeric_col:
        ts = cleaned_df[[date_col, numeric_col]].dropna().sort_values(date_col)
        if not ts.empty:
            monthly = ts.set_index(date_col)[numeric_col].resample("ME").mean().dropna()
            if len(monthly) >= 2:
                trend_chart = {
                    "column": numeric_col,
                    "date_column": date_col,
                    "points": [
                        {"label": idx.strftime("%b %Y"), "value": round(float(v), 2)}
                        for idx, v in monthly.items()
                    ],
                }

    return {
        "numeric_charts": numeric_charts,
        "category_charts": category_charts,
        "trend_chart": trend_chart,
    }


def _small_preview(preview: Any) -> Any:
    if isinstance(preview, dict):
        items = list(preview.items())[:6]
        return {str(k): (round(v, 2) if isinstance(v, (int, float)) else v) for k, v in items}
    return None


# --------------------------------------------------------------- model step


def _run_model(cleaned_df: pd.DataFrame, original_df: pd.DataFrame) -> dict:
    try:
        cfg = _model_config(cleaned_df, original_df)
    except ValueError as exc:
        return _model_unavailable(str(exc))

    work = cleaned_df.copy()
    for col in cfg["date_derived"]:
        work[f"{col}_month"] = pd.to_datetime(work[col], errors="coerce").dt.month

    try:
        result = select_and_fit_model(
            work,
            target_col=cfg["target"],
            feature_cols=cfg["features"],
            numeric_cols=cfg["numeric"],
            categorical_cols=cfg["categorical"],
        )
    except Exception as exc:  # noqa: BLE001 - modeling is best-effort on unknown data
        return _model_unavailable(f"the model step could not run on this data ({exc})")

    attempts = [
        {
            "model": e["model_tried"],
            "label": MODEL_LABELS.get(e["model_tried"], e["model_tried"]),
            "passed": bool(e["passed"]),
            "reason": plain_reason(e["reason"]),
            "cv_r2": e["eval"].get("cv_r2_mean"),
            "test_rmse": e["eval"].get("test_rmse"),
        }
        for e in result["model_log"]
    ]
    chosen = result["chosen_model"]
    obs = result["observation"]
    return {
        "available": True,
        "target": cfg["target"],
        "observation": {
            "n_samples": obs["n_samples"],
            "n_features": obs["n_features"],
            "linearity_signal": obs["linearity_signal"],
            "max_abs_correlation": obs["max_abs_correlation"],
        },
        "start_reason": plain_reason(result["start_reason"]),
        "attempts": attempts,
        "chosen": None if chosen is None else {
            "model": chosen["name"],
            "label": MODEL_LABELS.get(chosen["name"], chosen["name"]),
            "cv_r2": chosen["eval"].get("cv_r2_mean"),
            "explanation": MODEL_EXPLANATIONS.get(chosen["name"], ""),
        },
        "raw_model_log": result["model_log"],
    }


def _model_unavailable(reason: str) -> dict:
    return {
        "available": False,
        "reason": plain(reason),
        "attempts": [],
        "chosen": None,
        "raw_model_log": [],
    }


def _model_config(cleaned_df: pd.DataFrame, original_df: pd.DataFrame) -> dict:
    numeric_cols = [
        c for c in cleaned_df.columns
        if pd.api.types.is_numeric_dtype(cleaned_df[c]) and not _looks_like_id(cleaned_df, c)
    ]
    if not numeric_cols:
        raise ValueError("there is no numeric column to predict on this data")

    target = _pick_target(original_df, numeric_cols)
    date_cols = [c for c in cleaned_df.columns if pd.api.types.is_datetime64_any_dtype(cleaned_df[c])]

    features, numeric, categorical, date_derived = [], [], [], []
    for c in cleaned_df.columns:
        if c == target or _looks_like_id(cleaned_df, c):
            continue
        if pd.api.types.is_datetime64_any_dtype(cleaned_df[c]):
            date_derived.append(c)
            features.append(f"{c}_month")
            numeric.append(f"{c}_month")
        elif pd.api.types.is_numeric_dtype(cleaned_df[c]):
            features.append(c)
            numeric.append(c)
        elif cleaned_df[c].nunique(dropna=True) <= 25:
            features.append(c)
            categorical.append(c)

    if not features:
        raise ValueError("there are no usable features to model with on this data")
    return {
        "target": target,
        "features": features,
        "numeric": numeric,
        "categorical": categorical,
        "date_derived": date_derived,
    }


def _pick_target(original_df: pd.DataFrame, numeric_cols: list[str]) -> str:
    """Prefer the numeric column the agent had to impute: that is the column
    with the most genuine signal to model, and it matches the demo dataset."""
    best, best_missing = None, 0
    for c in numeric_cols:
        if c in original_df.columns:
            miss = int(original_df[c].isna().sum())
            if miss > best_missing:
                best, best_missing = c, miss
    if best:
        return best
    return max(numeric_cols, key=lambda c: original_df[c].std() if c in original_df else 0)


def _looks_like_id(df: pd.DataFrame, col: str) -> bool:
    name = col.lower()
    if name in ("id", "record_id", "row_id", "index") or name.endswith("_id"):
        return True
    return df[col].is_unique and pd.api.types.is_integer_dtype(df[col])


def _pick_group_col(df: pd.DataFrame) -> str | None:
    preferred = ("region", "category", "segment", "group", "type", "tier", "department")
    text_cols = [
        c for c in df.columns
        if (pd.api.types.is_string_dtype(df[c]) or pd.api.types.is_object_dtype(df[c]))
        and 2 <= df[c].nunique(dropna=True) <= 20
    ]
    for name in preferred:
        for c in text_cols:
            if name in c.lower():
                return c
    return text_cols[0] if text_cols else None


def _pick_numeric_col(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]) and not _looks_like_id(df, c):
            return c
    return None


def _pick_date_col(df: pd.DataFrame) -> str | None:
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    return None


# ---------------------------------------------------------------- lesson text


def _lesson(action_log: list[dict], model_log: list[dict]) -> str:
    import os  # noqa: PLC0415

    if os.environ.get("GEMINI_API_KEY"):
        try:
            from narrate_llm import generate_lesson  # noqa: PLC0415
            from schemas import ActionLogEntry, ModelLogEntry  # noqa: PLC0415

            actions = [ActionLogEntry(**e) for e in action_log]
            models = [ModelLogEntry(**e) for e in model_log]
            return plain(generate_lesson(actions, models))
        except Exception:  # noqa: BLE001 - narration is a nice-to-have, never fatal
            pass

    lines = ["## What happened to your data"]
    for e in action_log:
        verb = "worked" if e["passed"] else "was rejected"
        label = STRATEGY_LABELS.get(e["action_tried"], {}).get("name", e["action_tried"])
        lines.append(f"- On {e['column']}, {label} {verb}: {plain_reason(e['reason'])}")
    if model_log:
        lines.append("## Choosing a model")
        for e in model_log:
            verb = "kept" if e["passed"] else "set aside"
            label = MODEL_LABELS.get(e["model_tried"], e["model_tried"])
            lines.append(f"- {label} was {verb}: {plain_reason(e['reason'])}")
    return "\n".join(lines)
