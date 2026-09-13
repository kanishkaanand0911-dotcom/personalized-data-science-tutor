"""Learner-facing text: friendly names for the agent's internal strategy ids,
role-flavored analogies, and a sanitizer that keeps the agent's exact numbers
while dropping the typographic dashes the design voice bans.

The role only changes the flavor of an analogy. It never changes which issues
are found, which strategies are tried, or what the agent decides.
"""

from __future__ import annotations

import re

# --- friendly labels for the agent's strategy ids (from DECISION_TREE) ---

STRATEGY_LABELS: dict[str, dict[str, str]] = {
    "impute_median": {
        "name": "Median fill",
        "blurb": "Put the middle value into every blank cell.",
    },
    "impute_knn": {
        "name": "Nearest-neighbor fill",
        "blurb": "Estimate each blank from the rows that look most similar.",
    },
    "impute_mode": {
        "name": "Most-common fill",
        "blurb": "Put the most frequent label into every blank cell.",
    },
    "normalize_categories": {
        "name": "Merge label variants",
        "blurb": "Fold spellings and casing of the same thing into one label.",
    },
    "coerce_numeric_strings": {
        "name": "Parse text into numbers",
        "blurb": "Strip symbols like a dollar sign or a k suffix and read the number.",
    },
    "coerce_dates": {
        "name": "Standardize the dates",
        "blurb": "Read every date format into one real calendar date.",
    },
    "flag_for_human_review": {
        "name": "Hand back to a person",
        "blurb": "Stop guessing and flag the column for a human to look at.",
    },
}

ISSUE_TITLES: dict[str, str] = {
    "missing_numeric": "Missing numbers",
    "missing_categorical": "Missing labels",
    "label_inconsistency": "Inconsistent labels",
    "format_error_numeric": "Numbers stored as text",
    "format_error_date": "Mixed-up date formats",
}

CHECK_LABELS: dict[str, str] = {
    "aggregation": "Group and total it",
    "time_series": "Chart it over time",
    "chart_renders": "Draw a bar chart",
}

MODEL_LABELS: dict[str, str] = {
    "LinearRegression": "Straight-line model",
    "Ridge": "Straight-line model, steadied",
    "RandomForestRegressor": "Many-small-rules model",
    "GradientBoostingRegressor": "Stacked-corrections model",
}

# What each model type actually does, in plain language - not why it was
# picked for this dataset (that's start_reason/the per-attempt reasons),
# just what it mechanically is, so "predicting deal_value" isn't a black box.
MODEL_EXPLANATIONS: dict[str, str] = {
    "LinearRegression": (
        "It draws the single straight line through your data that stays closest to every "
        "point on average, then reads predictions straight off that line."
    ),
    "Ridge": (
        "The same straight-line idea, but it deliberately keeps the line a little flatter "
        "so one unusual row can't tilt the whole prediction too far."
    ),
    "RandomForestRegressor": (
        "It builds hundreds of simple yes/no rulebooks from random slices of your data, "
        "then averages all of their guesses into one prediction."
    ),
    "GradientBoostingRegressor": (
        "It builds one simple rulebook, looks at exactly where that one was wrong, then "
        "builds another rulebook that focuses on fixing those mistakes - repeated many times."
    ),
}


# --- role-flavored analogies. "default" always exists; roles override only tone. ---

_ANALOGIES: dict[str, dict[str, str]] = {
    "missing_numeric": {
        "default": (
            "Some rows have no number here. You could drop the same typical value into "
            "every gap, but when the real values run from small to very large, that one "
            "number quietly bends the whole shape of the column."
        ),
        "sales": (
            "Some deals have no value recorded. Pasting one average figure into every "
            "blank makes your pipeline look tidy, but it flattens the gap between a "
            "small renewal and a big enterprise deal."
        ),
        "operations": (
            "Some entries are missing a quantity. One filler value everywhere keeps the "
            "sheet full, but it hides the difference between a routine order and a spike."
        ),
        "hr": (
            "Some records have no figure here, like a blank salary or tenure. A single "
            "stand-in value everywhere blurs the range you actually care about."
        ),
        "student": (
            "Some rows are blank. Imagine filling every missing test score with the "
            "class average: the sheet looks complete, but the spread of results is gone."
        ),
    },
    "missing_categorical": {
        "default": (
            "Some rows have no label here. The safe guess is the label that shows up "
            "most often, which keeps the column usable without inventing a new category."
        ),
        "student": (
            "Some rows have no category filled in, like a missing subject. The usual "
            "move is to assume the most common one rather than guess something new."
        ),
    },
    "label_inconsistency": {
        "default": (
            "The same thing is written several ways: different casing, extra spaces, "
            "old names for the same place. To a computer these are all separate groups, "
            "so any total by group comes out wrong until they are merged."
        ),
        "sales": (
            "One region is spelled three different ways across the sheet. Your "
            "by-region numbers split across those spellings until they are treated as "
            "one region."
        ),
        "operations": (
            "The same site or category is entered inconsistently. Every report grouped "
            "by it is fragmented until the variants are folded together."
        ),
        "hr": (
            "The same department is written a few different ways. Headcount by "
            "department stays wrong until those variants collapse into one."
        ),
    },
    "format_error_numeric": {
        "default": (
            "This column holds numbers, but they are stored as text with symbols like a "
            "dollar sign, a comma, or a k for thousands. Nothing can add them up until "
            "they are read back as plain numbers."
        ),
        "sales": (
            "Revenue is written like text, with dollar signs and a k for thousands. You "
            "cannot sum a column of text, so it has to be parsed into real numbers first."
        ),
    },
    "format_error_date": {
        "default": (
            "The dates are written in more than one format in the same column. Sorting "
            "or charting by date needs them all read into one real calendar date first."
        ),
        "operations": (
            "Timestamps come in a few different formats. Any trend over time is "
            "unreliable until they are all parsed the same way."
        ),
    },
}


def analogy_for(issue_type: str, role: str | None) -> str:
    table = _ANALOGIES.get(issue_type, {})
    if not table:
        return ""
    key = (role or "").strip().lower()
    return table.get(key, table["default"])


# --- sanitizer: keep the agent's numbers, drop the dashes the voice bans ---

_REPLACEMENTS = [
    (" -- ", ", "),
    (" --", ","),
    ("-- ", ""),
    (" -> ", " to "),
    ("->", " to "),
    ("R^2", "R²"),
    ("—", ", "),
    ("–", "-"),
]


def plain(text: str) -> str:
    """Reword an already-correct backend string into the app voice without
    touching any figure inside it."""
    if not text:
        return ""
    out = text
    for a, b in _REPLACEMENTS:
        out = out.replace(a, b)
    out = re.sub(r"\s{2,}", " ", out).strip()
    out = re.sub(r"\s+([,.])", r"\1", out)
    if out and out[0].islower():
        out = out[0].upper() + out[1:]
    return out


# --- de-jargoning the agent's own pass/fail explanations -----------------
#
# app/agent/loop.py and app/modeling/model_selector.py write their reason
# strings in real statistical language (skew, thresholds, R^2, residual
# correlation) because that's genuinely what they checked - this app's
# learners are not data scientists, so those exact words shouldn't be the
# first thing they read. This only rewords the sentence; every number in it
# passes through untouched, and the underlying pass/fail decision (computed
# in app/, never here) is never touched at all.
#
# Each entry matches one of the small, fixed set of templates those two
# files actually emit. A reason that doesn't match any of them (a change to
# app/ this file doesn't know about yet) falls through to plain() unchanged
# rather than erroring - so this can only ever make known cases friendlier,
# never break on an unknown one.
_REASON_REWRITES: list[tuple[re.Pattern, str]] = [
    (
        re.compile(
            r"^skew shifted ([\d.]+)% \([-\d.]+ -> [-\d.]+\), "
            r"exceeds [\d.]+% threshold -- distribution distorted$"
        ),
        r"This fix changed the shape of the numbers by \1% - a big enough swing "
        r"that the agent backed it out rather than keep it.",
    ),
    (
        re.compile(r"^skew shift ([\d.]+)%, within [\d.]+% threshold$"),
        r"This fix only changed the shape of the numbers by \1% - close enough "
        r"to the original to trust.",
    ),
    (
        re.compile(r"^still has ([\d.]+)% nulls after imputation$"),
        r"\1% of the blanks were still empty even after this fix.",
    ),
    (
        re.compile(r"^unique labels reduced (\d+) -> (\d+)$"),
        r"Merged \1 different spellings of the same thing down to \2.",
    ),
    (
        re.compile(r"^unique count didn't decrease -- normalization had no effect$"),
        "Merging spellings didn't actually cut down how many different labels there were.",
    ),
    (
        re.compile(r"^column still doesn't parse as numeric after coercion$"),
        "The values still don't read as real numbers even after this fix.",
    ),
    (
        re.compile(r"^column now parses as numeric$"),
        "The values now read as real numbers the way they should.",
    ),
    (
        re.compile(r"^([\d.]+)% of dates failed to parse after coercion$"),
        r"\1% of the dates still didn't read correctly after standardizing them.",
    ),
    (
        re.compile(r"^dates parsed consistently$"),
        "Every date now reads in one consistent format.",
    ),
    (
        re.compile(
            r"^cross-validated R\^2 = ([-\d.]+) is below the [\d.]+ minimum -- "
            r"model isn't explaining enough variance$"
        ),
        r"Tested on data it hadn't seen, this model only explained about "
        r"\1 of the pattern (on a 0-to-1 scale) - not reliable enough to use.",
    ),
    (
        re.compile(
            r"^residuals correlate with predictions \(([-\d.]+)\) above [\d.]+ -- "
            r"model is systematically wrong in a structured way, not just noisy; "
            r"a more flexible model may capture this$"
        ),
        r"This model isn't just a little off randomly - its mistakes follow a "
        r"pattern, which usually means it's too simple for this data.",
    ),
    (
        re.compile(r"^R\^2=([-\d.]+), residuals look reasonably random \(corr=([-\d.]+)\) -- acceptable fit$"),
        r"This model explains about \1 of the pattern (on a 0-to-1 scale), and its "
        r"mistakes look like ordinary noise rather than a pattern it missed - a solid fit.",
    ),
    (
        re.compile(
            r"^strong linear correlation detected -- starting with the simplest model "
            r"that fits that pattern$"
        ),
        "Your columns move together in an almost straight line, so the agent "
        "starts with the simplest model that can draw one.",
    ),
    (
        re.compile(
            r"^linear correlation with target is (\w+) \(max \|corr\|=([-\d.]+)\) -- "
            r"still starting simple as a baseline, but expecting to escalate to a "
            r"model that can capture non-linear or interaction effects$"
        ),
        r"The relationship between your columns is \1, not a clean straight line, so "
        r"the agent starts simple as a baseline but expects to need a more flexible "
        r"model.",
    ),
]


def plain_reason(text: str) -> str:
    """plain(), plus rewording the agent's known statistical-jargon reason
    templates into plain language. See _REASON_REWRITES above."""
    stripped = (text or "").strip()
    for pattern, replacement in _REASON_REWRITES:
        if pattern.match(stripped):
            return plain(pattern.sub(replacement, stripped))
    return plain(text)
