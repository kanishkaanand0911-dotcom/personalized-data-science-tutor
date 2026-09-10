"""
Pairs each action/model name with the ACTUAL code that does it, plus one
plain-language sentence explaining that specific code. This is what "explain
the code" means concretely -- not a generic tutorial, the real lines from
this project that just ran, shown next to the case that used them.

Kept as a static lookup (not introspecting the live function source) so
the explanation text is stable and controlled -- reading raw function
source via inspect.getsource() would leak internal variable names/comments
not meant for an end user and could change wording unpredictably.
"""

from __future__ import annotations

CODE_SNIPPETS = {
    "impute_median": {
        "code": "median_val = out[column].median()\nout[column] = out[column].fillna(median_val)",
        "explain": "This finds the middle value of the column (half the numbers are above it, half below), then uses that single number to fill in every blank cell.",
    },
    "impute_knn": {
        "code": "imputer = KNNImputer(n_neighbors=5)\nimputed_block = imputer.fit_transform(out[numeric_cols])",
        "explain": "For each blank cell, this looks at the 5 rows that are most similar across other numeric columns, and fills in the blank using their average instead of one flat number for everyone.",
    },
    "impute_mode": {
        "code": "mode_val = out[column].mode(dropna=True)\nout[column] = out[column].fillna(mode_val.iloc[0])",
        "explain": "This finds the single most frequently occurring value in the column and uses it to fill in every blank cell.",
    },
    "normalize_categories": {
        "code": "normalized_vals = series.dropna().map(norm)\n# groups values whose normalized form is the same or very similar",
        "explain": "This compares every text value in the column to every other one, groups together the ones that are really the same thing (just typed differently), and relabels them all to match.",
    },
    "coerce_numeric_strings": {
        "code": 's = str(v).strip().replace(",", "").replace("$", "")\nreturn float(s)',
        "explain": "This strips out symbols like $ and commas from each value, then converts the leftover text into an actual number Python can do math with.",
    },
    "coerce_dates": {
        "code": 'out[column] = pd.to_datetime(out[column], errors="coerce", format="mixed")',
        "explain": "This reads each date regardless of how it was typed (12/05/2024, 2024-05-12, etc.) and converts it into one single, consistent date format.",
    },
    "LinearRegression": {
        "code": "model = LinearRegression()\nmodel.fit(X_train, y_train)",
        "explain": "This tries to draw the best possible straight line (or flat plane, with more than one input) through the data, and uses that line to make predictions.",
    },
    "Ridge": {
        "code": "model = Ridge(alpha=1.0)",
        "explain": "This works like a straight-line model, but it's deliberately a bit more cautious -- it shrinks large coefficients so the model doesn't overreact to any single column.",
    },
    "RandomForestRegressor": {
        "code": "model = RandomForestRegressor(n_estimators=200)",
        "explain": "This builds 200 different decision trees, each looking at the data slightly differently, then averages all their guesses together for a more robust prediction.",
    },
    "GradientBoostingRegressor": {
        "code": "model = GradientBoostingRegressor()",
        "explain": "This builds one small model, checks what it got wrong, builds another model specifically to fix those mistakes, and repeats -- each round improving on the last round's errors.",
    },
}


def get_code_snippet(action_or_model_name: str) -> dict | None:
    """Returns {"code": str, "explain": str} or None if we don't have one for this name."""
    return CODE_SNIPPETS.get(action_or_model_name)


if __name__ == "__main__":
    for name in ["impute_median", "impute_knn", "LinearRegression", "not_a_real_thing"]:
        snippet = get_code_snippet(name)
        print(f"\n{name}:")
        if snippet:
            print(f"  code: {snippet['code']}")
            print(f"  explains as: {snippet['explain']}")
        else:
            print("  (no snippet registered)")
