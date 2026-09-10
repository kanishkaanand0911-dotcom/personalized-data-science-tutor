"""
Action functions: one per cleaning strategy. Each takes (df, column, **kwargs)
and returns a NEW dataframe (copy) with that column modified -- never mutate
in place, since the agent loop needs to be able to revert on failure.
"""

import sys
import re
import pandas as pd
import numpy as np
from sklearn.impute import KNNImputer

sys.path.insert(0, "/home/claude/project")
from app.agent.detect import KNOWN_ALIASES, _normalize_for_clustering, LABEL_SIMILARITY_THRESHOLD
import difflib


# ---------------- Missing value strategies ----------------

def impute_median(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    median_val = out[column].median()
    out[column] = out[column].fillna(median_val)
    return out


def impute_knn(df: pd.DataFrame, column: str, n_neighbors: int = 5) -> pd.DataFrame:
    """
    KNN imputation using OTHER numeric columns as context, not just the
    column itself (that's the point of KNN over median -- it uses
    correlated columns to make a smarter guess per-row).
    """
    out = df.copy()
    numeric_cols = out.select_dtypes(include=[np.number]).columns.tolist()
    if column not in numeric_cols:
        numeric_cols.append(column)

    # Columns that had zero nulls before imputation don't need to go through
    # KNNImputer's fit/transform themselves -- but KNNImputer still needs them
    # as *context* (e.g. record_id correlating with deal_value patterns).
    # We restore their original dtype afterward since KNNImputer forces
    # everything to float, which looks wrong for an ID column that was never
    # actually missing anything.
    original_dtypes = {c: out[c].dtype for c in numeric_cols if out[c].isna().sum() == 0}

    if len(numeric_cols) < 2:
        # no other numeric columns to lean on -- fall back to median
        return impute_median(df, column)

    imputer = KNNImputer(n_neighbors=n_neighbors)
    imputed_block = imputer.fit_transform(out[numeric_cols])
    out[numeric_cols] = imputed_block

    for c, dtype in original_dtypes.items():
        if pd.api.types.is_integer_dtype(dtype):
            out[c] = out[c].round().astype(dtype)

    return out


def impute_mode(df: pd.DataFrame, column: str) -> pd.DataFrame:
    out = df.copy()
    mode_val = out[column].mode(dropna=True)
    if len(mode_val) > 0:
        out[column] = out[column].fillna(mode_val.iloc[0])
    return out


# ---------------- Label inconsistency strategy ----------------

def normalize_categories(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """
    Collapses casing/whitespace variants (via normalization) and known
    aliases (via KNOWN_ALIASES) to a single canonical label per cluster.
    The canonical label chosen per cluster = the most frequent raw value
    in that cluster (majority vote), title-cased for display.
    """
    out = df.copy()
    series = out[column]

    def norm(v):
        base = _normalize_for_clustering(v)
        return KNOWN_ALIASES.get(base, base)

    normalized_vals = series.dropna().map(norm)

    # cluster normalized forms that are still fuzzy-similar (catches leftover typos)
    unique_norms = normalized_vals.unique().tolist()
    rep_of = {}
    for n in unique_norms:
        assigned = None
        for existing in rep_of:
            if difflib.SequenceMatcher(None, n, existing).ratio() >= LABEL_SIMILARITY_THRESHOLD:
                assigned = rep_of[existing]
                break
        if assigned is None:
            assigned = n
        rep_of[n] = assigned

    # pick canonical display label per final cluster = most frequent raw value in it
    cluster_of_raw = {}
    for raw in series.dropna().unique():
        cluster_of_raw[raw] = rep_of[norm(raw)]

    counts_by_cluster = {}
    for raw, cluster in cluster_of_raw.items():
        cnt = (series == raw).sum()
        counts_by_cluster.setdefault(cluster, []).append((raw, cnt))

    canonical_label = {}
    for cluster, raw_counts in counts_by_cluster.items():
        best_raw = max(raw_counts, key=lambda x: x[1])[0]
        canonical_label[cluster] = str(best_raw).strip().title()

    out[column] = series.map(lambda v: canonical_label[cluster_of_raw[v]] if pd.notna(v) else v)
    return out


# ---------------- Format error strategies ----------------

def coerce_numeric_strings(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Strips $, commas, and 'k' suffix, converts to float."""
    out = df.copy()

    def clean(v):
        if pd.isna(v):
            return np.nan
        s = str(v).strip().replace(",", "").replace("$", "")
        if s.lower().endswith("k"):
            try:
                return float(s[:-1]) * 1000
            except ValueError:
                return np.nan
        try:
            return float(s)
        except ValueError:
            return np.nan

    out[column] = out[column].map(clean)
    return out


def coerce_dates(df: pd.DataFrame, column: str) -> pd.DataFrame:
    """Parses mixed date formats into a single consistent datetime dtype."""
    out = df.copy()
    out[column] = pd.to_datetime(out[column], errors="coerce", format="mixed")
    return out


if __name__ == "__main__":
    df = pd.read_csv("/mnt/user-data/outputs/messy_sales_dataset.csv")

    print("=== impute_median on deal_value ===")
    r1 = impute_median(df, "deal_value")
    print("nulls after:", r1["deal_value"].isna().sum(), "| skew after:", round(r1["deal_value"].skew(), 3))

    print("\n=== impute_knn on deal_value ===")
    r2 = impute_knn(df, "deal_value")
    print("nulls after:", r2["deal_value"].isna().sum(), "| skew after:", round(r2["deal_value"].skew(), 3))

    print("\n=== normalize_categories on city ===")
    r3 = normalize_categories(df, "city")
    print(r3["city"].value_counts())

    print("\n=== coerce_numeric_strings on revenue_display ===")
    r4 = coerce_numeric_strings(df, "revenue_display")
    print(r4["revenue_display"].head(5).tolist(), "| dtype:", r4["revenue_display"].dtype)

    print("\n=== coerce_dates on signup_date ===")
    r5 = coerce_dates(df, "signup_date")
    print(r5["signup_date"].head(5).tolist(), "| dtype:", r5["signup_date"].dtype)
    print("parse failures:", r5["signup_date"].isna().sum())
