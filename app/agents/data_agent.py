"""
DATA ANALYST AGENT

Responsibility: everything factual about the learner's dataset.

This agent is a thin coordinator over the ORIGINAL deterministic backend --
it deliberately adds no new statistics of its own:

    app.eda.explore          -> distributions, outliers, correlations
    app.agent.detect         -> rule-based issue detection
    app.agent.loop           -> the observe/decide/act/evaluate/adapt cleaning loop
    app.evaluation.downstream-> "is the cleaned data actually usable" checks
    app.modeling.model_selector -> the second agentic loop, for model choice
    app.modeling.column_roles   -> automatic feature-role detection
    app.modeling.feature_importance -> which columns drove the prediction

Nothing here asks an LLM for a number. Every figure the learner is later
taught traces back to pandas or scikit-learn running on their actual file.
"""

from __future__ import annotations

import os

import pandas as pd

from app.agents.base import Agent
from app.core.schemas import AgentResponse, DatasetAnalysis

# The original backend, reused as-is.
from app.agent.detect import detect_issues
from app.agent.loop import run_agent
from app.eda.explore import explore_dataset, explain_eda
from app.evaluation.stats import compute_stats
from app.evaluation.downstream import run_downstream_checks
from app.modeling.column_roles import auto_detect_feature_roles, ID_LIKE_PATTERN
from app.modeling.model_selector import select_and_fit_model
from app.modeling.feature_importance import get_feature_importance

# Column-name hints used to guess what a dataset is about, so the teacher can
# use the learner's own domain language. Purely a naming heuristic -- it never
# changes a computed number.
DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "sales": ("deal", "revenue", "sales", "quota", "pipeline", "opportunity", "account"),
    "marketing": ("campaign", "click", "impression", "conversion", "channel", "ctr", "spend"),
    "hr": ("employee", "attrition", "salary", "department", "tenure", "headcount", "hire"),
    "operations": ("shipment", "inventory", "delivery", "warehouse", "throughput", "stock"),
    "finance": ("cost", "budget", "expense", "transaction", "invoice", "profit"),
}


def _guess_domain(columns: list[str]) -> str | None:
    lowered = " ".join(c.lower() for c in columns)
    best, best_hits = None, 0
    for domain, hints in DOMAIN_HINTS.items():
        hits = sum(1 for h in hints if h in lowered)
        if hits > best_hits:
            best, best_hits = domain, hits
    return best if best_hits >= 1 else None


def pick_chart_columns(df: pd.DataFrame, preferred_numeric: str | None = None) -> dict:
    """
    Chooses which columns are actually worth charting.

    Two filters do the real work here. ID-like columns are dropped even though
    they are numerically valid, because a histogram of record_id teaches
    nothing; and categorical columns are ranked by how few distinct values they
    have, because a bar chart of 20 sales reps is unreadable while one of 5
    regions is the whole point.
    """
    id_like = {c for c in df.columns if ID_LIKE_PATTERN.search(c)}

    numeric = [c for c in df.select_dtypes(include="number").columns if c not in id_like]
    datetimes = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    categorical = [
        c for c in df.columns
        if c not in numeric and c not in datetimes and c not in id_like
        and 2 <= df[c].nunique(dropna=True) <= 20
    ]
    categorical.sort(key=lambda c: df[c].nunique(dropna=True))

    if preferred_numeric and preferred_numeric in numeric:
        numeric = [preferred_numeric] + [c for c in numeric if c != preferred_numeric]

    return {"numeric": numeric, "datetimes": datetimes, "categorical": categorical}


def _chart_opportunities(df: pd.DataFrame, preferred_numeric: str | None = None) -> list[dict]:
    """
    Which charts this dataset can genuinely support, with the columns to use.
    The visualization agent picks from this list -- it never proposes a chart
    the data cannot produce.
    """
    picked = pick_chart_columns(df, preferred_numeric)
    numeric, datetimes, categorical = picked["numeric"], picked["datetimes"], picked["categorical"]

    opportunities: list[dict] = []
    # One bar opportunity per usable category column, not just the first --
    # a learner who asks about "region" should get region, even when some
    # other column has fewer distinct values.
    if categorical and numeric:
        for cat in categorical[:4]:
            opportunities.append({
                "chart_type": "bar", "x": cat, "y": numeric[0],
                "question": f"How does {numeric[0]} compare across {cat}?",
                "reason": f"'{cat}' is a category with a small number of distinct values and "
                          f"'{numeric[0]}' is a number, which is exactly what a bar chart compares.",
            })
    if datetimes and numeric:
        opportunities.append({
            "chart_type": "line", "x": datetimes[0], "y": numeric[0],
            "question": f"How has {numeric[0]} changed over time?",
            "reason": f"'{datetimes[0]}' is a real date column, so the values can be put in time order -- "
                      f"that ordering is what makes a line meaningful rather than decorative.",
        })
    if numeric:
        opportunities.append({
            "chart_type": "histogram", "x": numeric[0], "y": None,
            "question": f"What does the spread of {numeric[0]} look like?",
            "reason": f"A histogram shows whether '{numeric[0]}' clusters around a typical value or "
                      f"is stretched out by a few extreme ones -- something an average alone hides.",
        })
    if len(numeric) >= 2:
        opportunities.append({
            "chart_type": "scatter", "x": numeric[0], "y": numeric[1],
            "question": f"Do {numeric[0]} and {numeric[1]} move together?",
            "reason": f"Both '{numeric[0]}' and '{numeric[1]}' are numbers, so each record can be a point "
                      f"and the shape of the cloud shows whether they are related.",
        })
    return opportunities


class DataAgent(Agent):
    name = "data_agent"
    responsibility = ("Understand the learner's dataset: structure, quality issues, EDA, cleaning "
                      "via the existing agentic loop, and model selection. All deterministic.")

    def analyze(self, df: pd.DataFrame, target_col: str | None = None,
                run_cleaning: bool = True, run_modeling: bool = True) -> DatasetAnalysis:
        """
        The full factual picture. Returns a DatasetAnalysis; raises nothing --
        each optional stage is guarded so one unsupported dataset shape cannot
        take down the whole analysis.
        """
        analysis = DatasetAnalysis(
            n_rows=len(df),
            n_cols=len(df.columns),
            columns=df.columns.tolist(),
            dtypes={c: str(df[c].dtype) for c in df.columns},
        )
        # Stats on the RAW frame -- this is the "before" picture the issue
        # detection and the cleaning lessons refer to.
        analysis.raw_column_stats = {c: compute_stats(df, c) for c in df.columns}
        analysis.column_stats = analysis.raw_column_stats
        analysis.suggested_domain = _guess_domain(analysis.columns)

        analysis.issues = [
            {"column": i.column, "issue_type": i.issue_type, "severity": i.severity, "details": i.details}
            for i in detect_issues(df)
        ]

        # EDA on the RAW data -- what a data scientist looks at before touching anything.
        try:
            analysis.eda = explore_dataset(df, target_col=target_col)
            analysis.eda["plain_summary"] = explain_eda(analysis.eda)
        except Exception as e:  # noqa: BLE001
            analysis.eda = {"error": str(e)}

        cleaned = df
        if run_cleaning:
            try:
                cleaned, action_log = run_agent(df, verbose=False)
                analysis.cleaning_log = action_log
            except Exception as e:  # noqa: BLE001
                analysis.cleaning_log = [{"error": str(e)}]

        analysis.chart_opportunities = _chart_opportunities(cleaned, preferred_numeric=target_col)
        # Re-read dtypes from the CLEANED frame: coerce_dates turns a string
        # column into a real datetime, and the curriculum's "can this dataset
        # support a line chart?" check depends on seeing that.
        analysis.dtypes = {c: str(cleaned[c].dtype) for c in cleaned.columns}
        analysis.columns = cleaned.columns.tolist()
        # column_stats describes the data the learner now HAS. Teaching
        # "'city' has 20 distinct values" after cleaning collapsed it to 5
        # would contradict the cleaning lesson two steps earlier.
        analysis.column_stats = {c: compute_stats(cleaned, c) for c in cleaned.columns}

        analysis.downstream = self._downstream(cleaned)

        if run_modeling and target_col:
            analysis.modeling = self._model(cleaned, target_col)

        self._cleaned_df = cleaned
        return analysis

    # ------------------------------------------------------------------ stages

    def _downstream(self, cleaned: pd.DataFrame) -> dict:
        """Runs the original downstream checks, picking suitable columns
        automatically rather than assuming the demo dataset's names."""
        picked = pick_chart_columns(cleaned)
        numeric, datetimes, categorical = picked["numeric"], picked["datetimes"], picked["categorical"]
        if not (numeric and datetimes and categorical):
            return {"skipped": "dataset does not have the category + number + date columns these checks need"}
        try:
            return run_downstream_checks(cleaned, group_col=categorical[0],
                                          numeric_col=numeric[0], date_col=datetimes[0])
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

    def _model(self, cleaned: pd.DataFrame, target_col: str) -> dict:
        """Runs the original model-selection loop with automatically detected
        feature roles, so it works on any uploaded file, not just the demo CSV."""
        if target_col not in cleaned.columns:
            return {"skipped": f"target column '{target_col}' is not in the dataset"}

        frame = cleaned.copy()
        # Derive a numeric feature from each date column: column_roles drops
        # datetimes, so without this a dataset's time information is lost to
        # the model entirely.
        for col in list(frame.columns):
            if pd.api.types.is_datetime64_any_dtype(frame[col]):
                frame[f"{col}_month"] = frame[col].dt.month
                frame = frame.drop(columns=[col])

        roles = auto_detect_feature_roles(frame, target_col=target_col)
        if not roles["feature_cols"]:
            return {"skipped": "no usable feature columns were found for this target"}
        if not pd.api.types.is_numeric_dtype(frame[target_col]):
            return {"skipped": f"'{target_col}' is not numeric -- the model selector supports regression only"}

        frame = frame.dropna(subset=[target_col])
        try:
            result = select_and_fit_model(
                frame, target_col=target_col,
                feature_cols=roles["feature_cols"],
                numeric_cols=roles["numeric_cols"],
                categorical_cols=roles["categorical_cols"],
            )
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)}

        importance = []
        if result.get("chosen_model"):
            try:
                importance = get_feature_importance(result["chosen_model"], roles["categorical_cols"])
            except Exception:  # noqa: BLE001
                importance = []

        return {
            "target": target_col,
            "roles": roles,
            "observation": result["observation"],
            "start_reason": result["start_reason"],
            "model_log": result["model_log"],
            "chosen_model_name": result["chosen_model"]["name"] if result["chosen_model"] else None,
            "chosen_model_eval": result["chosen_model"]["eval"] if result["chosen_model"] else None,
            "all_candidates_considered": result.get("all_candidates_considered", []),
            "feature_importance": importance,
        }

    # ------------------------------------------------------------------ agent api

    def run(self, df: pd.DataFrame | None = None, csv_path: str | None = None,
            target_col: str | None = None, **kwargs) -> AgentResponse:
        if df is None:
            if not csv_path or not os.path.exists(csv_path):
                return self._respond("analyze_data", "I don't have a dataset to look at yet. "
                                      "Upload a CSV and I'll analyse it.", {"analysis": None})
            df = pd.read_csv(csv_path)

        analysis = self.analyze(df, target_col=target_col)
        return self._respond("analyze_data", self.summarize(analysis),
                             {"analysis": analysis.to_dict()}, used_llm=False)

    # ------------------------------------------------------------------ narration

    def summarize(self, analysis: DatasetAnalysis) -> str:
        """
        Plain-language summary built only from computed facts. This is the
        deterministic version; the teacher agent may reword it with an LLM,
        but the numbers can only come from here.
        """
        lines = [f"Your file has {analysis.n_rows} rows and {analysis.n_cols} columns."]
        if analysis.suggested_domain:
            lines.append(f"The column names look like {analysis.suggested_domain} data.")

        if analysis.issues:
            by_type: dict[str, list[str]] = {}
            for issue in analysis.issues:
                by_type.setdefault(issue["issue_type"], []).append(issue["column"])
            described = "; ".join(
                f"{t.replace('_', ' ')} in {', '.join(cols)}" for t, cols in by_type.items()
            )
            lines.append(f"I found {len(analysis.issues)} data quality issue(s): {described}.")
        else:
            lines.append("I did not find any data quality issues worth flagging.")

        fixed = [e for e in analysis.cleaning_log if e.get("passed")]
        retried = [e for e in analysis.cleaning_log if not e.get("passed")]
        if fixed:
            lines.append(f"I fixed {len(fixed)} of them" +
                          (f", after {len(retried)} attempt(s) that failed the quality check and were rolled back."
                           if retried else "."))

        if analysis.eda.get("plain_summary"):
            lines.append(analysis.eda["plain_summary"])

        if analysis.chart_opportunities:
            # There is one bar opportunity per category column, so the types
            # must be de-duplicated before they are listed to the learner.
            charts = ", ".join(dict.fromkeys(o["chart_type"] for o in analysis.chart_opportunities))
            lines.append(f"Charts your data can support: {charts}.")

        model_name = analysis.modeling.get("chosen_model_name")
        if model_name:
            r2 = (analysis.modeling.get("chosen_model_eval") or {}).get("cv_r2_mean")
            lines.append(f"For predicting {analysis.modeling['target']}, {model_name} was selected"
                          + (f" (cross-validated R-squared {r2})." if r2 is not None else "."))
        return " ".join(lines)
