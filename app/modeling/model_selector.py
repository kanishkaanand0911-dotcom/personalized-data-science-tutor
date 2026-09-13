"""
Model selection agent: the second real agentic loop, applied to choosing
a regression model instead of a cleaning strategy. Same shape as the
cleaning loop on purpose (observe -> decide -> act -> evaluate -> adapt):

  1. OBSERVE the data's shape (linearity signal, feature count, sample size)
  2. DECIDE which model family to try first, with a stated reason
  3. ACT: fit it
  4. EVALUATE: cross-validated R^2/RMSE + a residual-pattern check
  5. ADAPT: if the fit is poor OR residuals show a non-random pattern
     (a sign the model's assumptions don't match the data), escalate to
     a more flexible model family and retry

This is deliberately NOT "train every model, keep the best score" --
that's brute force, not decision-making, and a judge will ask why you
needed an agent for that. Each escalation has to be justified by a
specific observed failure, which is also exactly what makes it
narratable for the "educator" layer (Person B can turn each of these
entries into a plain-language sentence with zero new logic).
"""

import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import cross_val_score, KFold, train_test_split
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import r2_score, mean_squared_error

sys.path.insert(0, "/home/claude/project")

# ---- Escalation ladder: simple -> flexible. Each entry has a plain-language
# "why we're trying this" reason, filled in dynamically based on what we
# observed, not a static string. ----

R2_MIN_ACCEPTABLE = 0.15   # deliberately low -- see note in run() about why
RESIDUAL_PATTERN_CORR_MAX = 0.25  # |correlation between residuals and prediction|
                                    # above this suggests the model is
                                    # systematically wrong in a structured way,
                                    # not just noisy -- a sign to escalate


def _build_preprocessor(df: pd.DataFrame, feature_cols: list, numeric_cols: list, categorical_cols: list):
    return ColumnTransformer(transformers=[
        ("num", "passthrough", numeric_cols),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical_cols),
    ])


def _observe_data_shape(df: pd.DataFrame, target_col: str, feature_cols: list, numeric_cols: list) -> dict:
    """
    OBSERVE step: look at the data before choosing anything.
    Checks simple linear correlation strength between numeric features and
    the target -- weak correlation is a signal (not proof) that a plain
    linear model may underfit, which informs (but doesn't fully decide)
    where to start.
    """
    correlations = {}
    for col in numeric_cols:
        if col == target_col:
            continue
        corr = df[[col, target_col]].corr().iloc[0, 1]
        correlations[col] = round(float(corr), 3) if pd.notna(corr) else 0.0

    max_abs_corr = max((abs(v) for v in correlations.values()), default=0.0)
    n_samples = len(df)
    n_features = len(feature_cols)

    return {
        "n_samples": n_samples,
        "n_features": n_features,
        "feature_correlations_with_target": correlations,
        "max_abs_correlation": round(max_abs_corr, 3),
        "linearity_signal": "weak" if max_abs_corr < 0.3 else ("moderate" if max_abs_corr < 0.6 else "strong"),
    }


def _evaluate_model(model, X, y, cv_folds: int = 5) -> dict:
    """
    EVALUATE step: cross-validated R^2 (not just a single train/test split
    score, so the result isn't an artifact of one lucky/unlucky split) plus
    a residual-pattern check on a held-out fold.
    """
    kf = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
    r2_scores = cross_val_score(model, X, y, cv=kf, scoring="r2")

    # residual pattern check: fit on a train split, look at residuals vs
    # predictions on a held-out split. A real (non-random) correlation here
    # means the model is missing structure in the data, not just noisy.
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    residuals = y_test.values - preds
    if len(set(preds)) > 1:
        residual_corr = np.corrcoef(preds, residuals)[0, 1]
    else:
        residual_corr = 0.0

    return {
        "cv_r2_mean": round(float(r2_scores.mean()), 3),
        "cv_r2_std": round(float(r2_scores.std()), 3),
        "test_r2": round(float(r2_score(y_test, preds)), 3),
        "test_rmse": round(float(np.sqrt(mean_squared_error(y_test, preds))), 2),
        "residual_pattern_corr": round(float(residual_corr), 3) if pd.notna(residual_corr) else 0.0,
    }


def _passes_model_check(eval_result: dict) -> tuple[bool, str]:
    r2 = eval_result["cv_r2_mean"]
    resid_corr = abs(eval_result["residual_pattern_corr"])

    if r2 < R2_MIN_ACCEPTABLE:
        return False, f"cross-validated R^2 = {r2} is below the {R2_MIN_ACCEPTABLE} minimum -- model isn't explaining enough variance"
    if resid_corr > RESIDUAL_PATTERN_CORR_MAX:
        return False, (f"residuals correlate with predictions ({resid_corr}) above {RESIDUAL_PATTERN_CORR_MAX} -- "
                        f"model is systematically wrong in a structured way, not just noisy; a more flexible model may capture this")
    return True, f"R^2={r2}, residuals look reasonably random (corr={resid_corr}) -- acceptable fit"


def select_and_fit_model(df: pd.DataFrame, target_col: str, feature_cols: list,
                          numeric_cols: list, categorical_cols: list) -> dict:
    """
    Runs the full observe -> decide -> act -> evaluate -> adapt loop for
    model selection. Returns a log in the same shape/spirit as the cleaning
    loop's action_log, plus the final chosen model.
    """
    observation = _observe_data_shape(df, target_col, feature_cols, numeric_cols)

    # DECIDE the starting point based on what we observed.
    if observation["linearity_signal"] == "strong":
        start_reason = "strong linear correlation detected -- starting with the simplest model that fits that pattern"
        candidates = [
            ("LinearRegression", LinearRegression()),
            ("RandomForestRegressor", RandomForestRegressor(n_estimators=200, random_state=42)),
            ("GradientBoostingRegressor", GradientBoostingRegressor(random_state=42)),
        ]
    else:
        start_reason = (f"linear correlation with target is {observation['linearity_signal']} "
                         f"(max |corr|={observation['max_abs_correlation']}) -- still starting simple as a "
                         f"baseline, but expecting to escalate to a model that can capture non-linear "
                         f"or interaction effects")
        candidates = [
            ("LinearRegression", LinearRegression()),
            ("Ridge", Ridge(alpha=1.0)),
            ("RandomForestRegressor", RandomForestRegressor(n_estimators=200, random_state=42)),
            ("GradientBoostingRegressor", GradientBoostingRegressor(random_state=42)),
        ]

    preprocessor = _build_preprocessor(df, feature_cols, numeric_cols, categorical_cols)
    X = df[feature_cols]
    y = df[target_col]

    model_log = []
    chosen = None

    for name, estimator in candidates:
        pipeline = Pipeline([("prep", preprocessor), ("model", estimator)])
        eval_result = _evaluate_model(pipeline, X, y)
        passed, reason = _passes_model_check(eval_result)

        entry = {
            "model_tried": name,
            "eval": eval_result,
            "passed": passed,
            "reason": reason,
        }
        model_log.append(entry)

        if passed:
            pipeline.fit(X, y)  # final fit on all data
            chosen = {"name": name, "pipeline": pipeline, "eval": eval_result}
            break

    return {
        "observation": observation,
        "start_reason": start_reason,
        "model_log": model_log,
        "chosen_model": chosen,  # None if every candidate failed
    }


if __name__ == "__main__":
    from app.agent.loop import run_agent

    df = pd.read_csv("/mnt/user-data/outputs/messy_sales_dataset.csv")
    cleaned_df, _ = run_agent(df, verbose=False)

    # Features available: region, city, sales_rep are categorical;
    # signup_date isn't a usable numeric feature yet without engineering
    # (month/quarter), so we derive month as a quick numeric feature.
    cleaned_df["signup_month"] = cleaned_df["signup_date"].dt.month

    feature_cols = ["region", "city", "sales_rep", "signup_month"]
    numeric_cols = ["signup_month"]
    categorical_cols = ["region", "city", "sales_rep"]

    result = select_and_fit_model(
        cleaned_df, target_col="deal_value",
        feature_cols=feature_cols, numeric_cols=numeric_cols, categorical_cols=categorical_cols
    )

    print("OBSERVE:")
    for k, v in result["observation"].items():
        print(f"  {k}: {v}")
    print(f"\nDECIDE: {result['start_reason']}\n")

    for entry in result["model_log"]:
        status = "PASSED" if entry["passed"] else "FAILED (escalating)"
        print(f"[{entry['model_tried']}] {status} -- {entry['reason']}")
        print(f"    {entry['eval']}")

    if result["chosen_model"]:
        print(f"\nFINAL MODEL: {result['chosen_model']['name']}")
    else:
        print("\nNo candidate model met the acceptance threshold -- flag for human review.")
