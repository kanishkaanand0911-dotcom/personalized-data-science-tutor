"""
Scans every column and detects missing values, inconsistent labels and format errors.
"""

import difflib
import re
import pandas as pd
from app.evaluation.stats import compute_stats
from app.agent.issue import Issue

MISSING_PCT_THRESHOLD = 5.0
LABEL_CARDINALITY_MAX_RATIO = 0.3
LABEL_SIMILARITY_THRESHOLD = 0.85
STRUCTURED_ID_MIN_FRACTION = 0.9
KNOWN_ALIASES = {
    "bombay": "mumbai", "madras": "chennai", "bangalore": "bengaluru",
    "poona": "pune", "new delhi": "delhi",
}
_STRUCTURED_ID_PATTERN = re.compile(r"^[A-Za-z]+[_\-\s]?\d+$")

def _looks_like_structured_id_column(raw_values: list) -> bool:
    return bool(raw_values) and sum(1 for v in raw_values if _STRUCTURED_ID_PATTERN.match(str(v).strip())) / len(raw_values) >= STRUCTURED_ID_MIN_FRACTION

def _normalize_for_clustering(value: str) -> str:
    return str(value).strip().lower()

def _cluster_labels(raw_values: list[str]) -> dict:
    unique_raw = list(dict.fromkeys(raw_values))
    normalized = {v: KNOWN_ALIASES.get(_normalize_for_clustering(v), _normalize_for_clustering(v)) for v in unique_raw}
    clusters, cluster_id_of, next_id = {}, {}, 0
    for v in unique_raw:
        norm_v = normalized[v]
        assigned = next((cid for existing, cid in clusters.items() if norm_v == existing), None)
        if assigned is None:
            for existing, cid in clusters.items():
                if difflib.SequenceMatcher(None, norm_v, existing).ratio() >= LABEL_SIMILARITY_THRESHOLD:
                    assigned = cid
                    break
        if assigned is None:
            assigned = next_id
            next_id += 1
            clusters[norm_v] = assigned
        cluster_id_of[v] = assigned
    return cluster_id_of

def detect_issues(df: pd.DataFrame) -> list[Issue]:
    issues = []
    for column in df.columns:
        stats = compute_stats(df, column)
        series = df[column]

        if stats["null_pct"] > MISSING_PCT_THRESHOLD:
            severity = "high" if stats["null_pct"] > 30 else ("medium" if stats["null_pct"] > 15 else "low")
            issues.append(Issue(
                column=column,
                issue_type="missing_numeric" if stats["skew"] is not None else "missing_categorical",
                severity=severity,
                details={"null_pct": stats["null_pct"], "before_stats": stats},
            ))

        is_text = pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)
        cardinality_ratio = stats["unique_count"] / stats["n_rows"] if stats["n_rows"] else 1
        if is_text and cardinality_ratio <= LABEL_CARDINALITY_MAX_RATIO:
            raw_values = series.dropna().tolist()
            if not _looks_like_structured_id_column(raw_values):
                cluster_map = _cluster_labels(raw_values)
                if len(set(cluster_map.values())) < stats["unique_count"]:
                    issues.append(Issue(
                        column=column, issue_type="label_inconsistency", severity="medium",
                        details={"raw_label_count": stats["unique_count"], "cluster_count_after_fuzzy_match": len(set(cluster_map.values())), "before_stats": stats},
                    ))

        if is_text and cardinality_ratio > LABEL_CARDINALITY_MAX_RATIO:
            non_null = series.dropna()
            if len(non_null) == 0:
                continue
            def try_numeric(v):
                s = str(v).strip().replace(",", "").replace("$", "")
                if s.lower().endswith("k"):
                    try: return float(s[:-1]) * 1000
                    except ValueError: return None
                try: return float(s)
                except ValueError: return None

            numeric_success = non_null.map(try_numeric).notna().mean()
            raw_numeric_success = pd.to_numeric(non_null, errors="coerce").notna().mean()
            date_success = pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean()

            if raw_numeric_success < 0.9 and numeric_success > 0.9:
                issues.append(Issue(column=column, issue_type="format_error_numeric", severity="medium",
                    details={"raw_parse_success": round(raw_numeric_success,2), "cleaned_parse_success": round(numeric_success,2), "before_stats": stats}))
            elif date_success > 0.9:
                sample_formats = non_null.sample(min(20, len(non_null)), random_state=1)
                if sample_formats.map(lambda x: len(str(x))).nunique() > 1:
                    issues.append(Issue(column=column, issue_type="format_error_date", severity="medium",
                        details={"date_parse_success": round(date_success,2), "before_stats": stats}))
    return issues
