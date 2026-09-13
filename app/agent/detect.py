"""
detect_issues(df): scans every column and returns a list of Issue objects
for exactly the 3 categories we scoped: missing values, label inconsistency,
and format errors (numbers/dates stored as inconsistently-formatted strings).

Deliberately rule-based, not LLM-based -- fast, auditable, no API cost per
column, and it's what a judge can actually follow on a slide.
"""

import sys
import difflib
import pandas as pd

sys.path.insert(0, "/home/claude/project")
from app.evaluation.stats import compute_stats
from app.agent.issue import Issue

# ---- thresholds (tune these once you see real behavior -- see notes below) ----
MISSING_PCT_THRESHOLD = 5.0          # below this, don't bother flagging
LABEL_CARDINALITY_MAX_RATIO = 0.3     # skip columns where unique/n_rows is too high
                                       # (those are probably free-text/dates/ids, not categories)
LABEL_SIMILARITY_THRESHOLD = 0.85     # difflib ratio above which two labels are
                                       # considered "the same thing, different casing"
STRUCTURED_ID_MIN_FRACTION = 0.9      # if >=90% of values match a "word_number"-style
                                       # pattern, treat the column as an ID, not a
                                       # free-text category -- skip fuzzy clustering
                                       # (difflib false-positives on "Rep_1" vs "Rep_12")

# Known real-world aliases that string-similarity can never catch, since the
# words themselves aren't similar (e.g. "Bombay" vs "Mumbai"). Extend as needed.
KNOWN_ALIASES = {
    "bombay": "mumbai",
    "madras": "chennai",
    "bangalore": "bengaluru",
    "poona": "pune",
    "new delhi": "delhi",
}

import re
_STRUCTURED_ID_PATTERN = re.compile(r"^[A-Za-z]+[_\-\s]?\d+$")


def _looks_like_structured_id_column(raw_values: list) -> bool:
    if not raw_values:
        return False
    matches = sum(1 for v in raw_values if _STRUCTURED_ID_PATTERN.match(str(v).strip()))
    return (matches / len(raw_values)) >= STRUCTURED_ID_MIN_FRACTION


def _normalize_for_clustering(value: str) -> str:
    """Casing/whitespace normalization used before fuzzy comparison."""
    return str(value).strip().lower()


def _cluster_labels(raw_values: list[str]) -> dict:
    """
    Very simple fuzzy clustering using stdlib difflib (rapidfuzz substitute --
    see note in the message accompanying this code).

    Returns {raw_value: cluster_id}. Two raw values land in the same cluster
    if their normalized forms are identical OR their similarity ratio clears
    LABEL_SIMILARITY_THRESHOLD.

    IMPORTANT LIMITATION: this only catches casing/whitespace/typo-level
    variants (e.g. "Mumbai" / "mumbai" / "MUMBAI"). It will NOT catch
    semantic aliases with different spelling, like "Bombay" -> "Mumbai" or
    "Madras" -> "Chennai" or "Bangalore" -> "Bengaluru" -- those need a
    manual alias table, not string similarity, because the strings
    themselves aren't similar. Flagging this explicitly for you to decide
    on, rather than silently under-cleaning the city column.
    """
    unique_raw = list(dict.fromkeys(raw_values))  # preserve order, dedupe

    def norm(v):
        base = _normalize_for_clustering(v)
        return KNOWN_ALIASES.get(base, base)

    normalized = {v: norm(v) for v in unique_raw}

    clusters = {}   # normalized_or_representative -> cluster_id
    cluster_id_of = {}
    next_id = 0

    for v in unique_raw:
        norm_v = normalized[v]
        assigned = None
        # exact normalized match first
        for existing_norm, cid in clusters.items():
            if norm_v == existing_norm:
                assigned = cid
                break
        if assigned is None:
            # fuzzy match against existing cluster representatives
            for existing_norm, cid in clusters.items():
                ratio = difflib.SequenceMatcher(None, norm_v, existing_norm).ratio()
                if ratio >= LABEL_SIMILARITY_THRESHOLD:
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

        # --- 1. Missing values ---
        if stats["null_pct"] > MISSING_PCT_THRESHOLD:
            severity = "high" if stats["null_pct"] > 30 else (
                "medium" if stats["null_pct"] > 15 else "low"
            )
            # Only meaningful to impute if it's genuinely numeric
            is_numeric = stats["skew"] is not None
            issues.append(Issue(
                column=column,
                issue_type="missing_numeric" if is_numeric else "missing_categorical",
                severity=severity,
                details={"null_pct": stats["null_pct"], "before_stats": stats},
            ))

        # --- 2. Label inconsistency (only for lowish-cardinality text columns) ---
        is_text = pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series)
        cardinality_ratio = stats["unique_count"] / stats["n_rows"] if stats["n_rows"] else 1
        if is_text and cardinality_ratio <= LABEL_CARDINALITY_MAX_RATIO:
            raw_values = series.dropna().tolist()
            if _looks_like_structured_id_column(raw_values):
                continue  # e.g. "Rep_1".."Rep_20" -- already consistent, not a label issue
            cluster_map = _cluster_labels(raw_values)
            n_clusters = len(set(cluster_map.values()))
            n_raw_labels = stats["unique_count"]
            if n_clusters < n_raw_labels:
                issues.append(Issue(
                    column=column,
                    issue_type="label_inconsistency",
                    severity="medium",
                    details={
                        "raw_label_count": n_raw_labels,
                        "cluster_count_after_fuzzy_match": n_clusters,
                        "before_stats": stats,
                    },
                ))

        # --- 3. Format errors: values that look like they should be numeric
        #         or date, but the column is stored as inconsistent strings ---
        if is_text and cardinality_ratio > LABEL_CARDINALITY_MAX_RATIO:
            non_null = series.dropna()
            if len(non_null) == 0:
                continue

            # try clean numeric parse (strip $, commas, "k" suffix) vs raw parse
            def try_numeric(v):
                s = str(v).strip().replace(",", "").replace("$", "")
                if s.lower().endswith("k"):
                    try:
                        return float(s[:-1]) * 1000
                    except ValueError:
                        return None
                try:
                    return float(s)
                except ValueError:
                    return None

            numeric_success = non_null.map(try_numeric).notna().mean()
            raw_numeric_success = pd.to_numeric(non_null, errors="coerce").notna().mean()

            date_success = pd.to_datetime(non_null, errors="coerce", format="mixed").notna().mean()

            if raw_numeric_success < 0.9 and numeric_success > 0.9:
                issues.append(Issue(
                    column=column,
                    issue_type="format_error_numeric",
                    severity="medium",
                    details={"raw_parse_success": round(raw_numeric_success, 2),
                             "cleaned_parse_success": round(numeric_success, 2),
                             "before_stats": stats},
                ))
            elif date_success > 0.9:
                # check whether formats are actually inconsistent (not just "it's a date column")
                sample_formats = non_null.sample(min(20, len(non_null)), random_state=1)
                distinct_lengths = sample_formats.map(lambda x: len(str(x))).nunique()
                if distinct_lengths > 1:
                    issues.append(Issue(
                        column=column,
                        issue_type="format_error_date",
                        severity="medium",
                        details={"date_parse_success": round(date_success, 2),
                                 "before_stats": stats},
                    ))

    return issues


if __name__ == "__main__":
    df = pd.read_csv("/mnt/user-data/outputs/messy_sales_dataset.csv")
    found = detect_issues(df)
    print(f"Found {len(found)} issues:\n")
    for i in found:
        print(i)
        print()
