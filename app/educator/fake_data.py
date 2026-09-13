"""
Fake log entries matching A's real schema exactly. Once real action_log /
model_log output exists, swap the import in test_harness.py and
narrate_llm.py's __main__ block — nothing else should need to change.
"""

from schemas import ActionLogEntry, ModelLogEntry

FAKE_ACTION_LOG = [
    ActionLogEntry(
        column="revenue", issue_type="missing", action_tried="impute_median",
        before_stats={"null_pct": 12.3, "skew": 2.1},
        after_stats={"null_pct": 0.0, "skew": 3.4},
        passed=False,
        reason="skew increased from 2.1 to 3.4 after imputation, exceeding the 0.5 tolerance",
    ),
    ActionLogEntry(
        column="revenue", issue_type="missing", action_tried="impute_knn",
        before_stats={"null_pct": 12.3, "skew": 2.1},
        after_stats={"null_pct": 0.0, "skew": 2.3},
        passed=True,
        reason="skew only moved from 2.1 to 2.3, within the 0.5 tolerance",
    ),
    ActionLogEntry(
        column="region", issue_type="categorical_inconsistency", action_tried="normalize_categories",
        before_stats={"unique_count": 7}, after_stats={"unique_count": 3},
        passed=True,
        reason="collapsed 7 label variants down to 3 canonical categories",
    ),
    ActionLogEntry(
        column="customer_notes", issue_type="missing", action_tried="flag_for_human_review",
        before_stats={"null_pct": 34.0}, after_stats={"null_pct": 34.0},
        passed=False,
        reason="all candidate strategies exhausted; 34% missing is too high to impute safely",
    ),
]

FAKE_MODEL_LOG = [
    ModelLogEntry(
        model_tried="linear_regression",
        eval={"cv_r2_mean": 0.42, "test_r2": 0.39, "residual_pattern_corr": 0.31},
        passed=False,
        reason="residual_pattern_corr of 0.31 exceeds the 0.2 threshold, meaning the model is missing a real pattern in the data",
    ),
    ModelLogEntry(
        model_tried="random_forest",
        eval={"cv_r2_mean": 0.71, "test_r2": 0.68, "residual_pattern_corr": 0.05},
        passed=True,
        reason="residual_pattern_corr of 0.05 is near zero and cv/test scores are close, indicating a stable fit",
    ),
]
