"""
The curriculum engine: (role, experience_level, goal) -> an ordered LearningPath.

This is deterministic on purpose. A learner's roadmap is the one thing that
must be stable, reviewable and defensible -- "why am I being taught this?"
should have a concrete answer, not "the model decided". The LLM's job comes
later, in how each lesson is *taught*, not in what the sequence is.

How the three inputs combine:
  - the GOAL picks a spine of concepts (the pedagogical order)
  - the ROLE swaps in the vocabulary, examples and role-specific concepts
    (an HR learner gets attrition and headcount, a sales learner gets regions
    and deal size) and can prepend concepts their job makes urgent
  - the EXPERIENCE LEVEL trims from the front and extends at the end -- an
    advanced learner never sees "what is a row", a beginner never reaches
    hyperparameter tuning
"""

from __future__ import annotations

from app.core.schemas import Lesson, LearningPath, UserProfile

# ------------------------------------------------------------------ concept library
# Every concept the platform can teach. `level` is the lowest experience level
# the concept is worth showing to -- that's what lets one spine serve all three
# levels without writing three separate curricula.

CONCEPTS: dict[str, dict] = {
    "rows_and_columns": {
        "title": "Rows and columns: what your data actually is",
        "objective": "Read a table confidently: what one row means, what one column means.",
        "level": "beginner", "needs_dataset": True,
    },
    "column_meanings": {
        "title": "What each of your columns means",
        "objective": "Say out loud what every column in your own file is recording.",
        "level": "beginner", "needs_dataset": True,
    },
    "data_types": {
        "title": "Numbers, text and dates",
        "objective": "Tell which columns can be added up and which can only be counted or grouped.",
        "level": "beginner", "needs_dataset": True,
    },
    "descriptive_stats": {
        "title": "Averages, spread and typical values",
        "objective": "Read a summary of a column and know what the average is hiding.",
        "level": "beginner", "needs_dataset": True,
    },
    "missing_values": {
        "title": "Missing values and what to do about them",
        "objective": "Spot blank cells and choose a filling strategy that doesn't distort the data.",
        "level": "beginner", "needs_dataset": True,
    },
    "duplicates": {
        "title": "Duplicate rows",
        "objective": "Find repeated records and decide whether they are errors or real.",
        "level": "beginner", "needs_dataset": True,
    },
    "inconsistent_categories": {
        "title": "The same thing spelled five different ways",
        "objective": "Recognise label variants and merge them into one clean category.",
        "level": "beginner", "needs_dataset": True,
    },
    "formatting_errors": {
        "title": "Numbers and dates trapped as text",
        "objective": "Spot values a computer cannot do maths with, and convert them.",
        "level": "beginner", "needs_dataset": True,
    },
    "outliers": {
        "title": "Outliers: the values that don't belong",
        "objective": "Find extreme values and judge whether they are mistakes or the real story.",
        "level": "beginner", "needs_dataset": True,
    },
    "cleaning_decisions": {
        "title": "Why each cleaning decision was made",
        "objective": "Justify a cleaning choice and explain what you traded away.",
        "level": "intermediate", "needs_dataset": True,
    },
    "bar_chart": {
        "title": "Comparing categories with a bar chart",
        "objective": "Build a bar chart and read the comparison it shows.",
        "level": "beginner", "needs_dataset": True, "chart_type": "bar",
    },
    "line_chart": {
        "title": "Showing change over time with a line chart",
        "objective": "Build a line chart over a date column and describe the trend.",
        "level": "beginner", "needs_dataset": True, "chart_type": "line",
    },
    "histogram": {
        "title": "Seeing a column's shape with a histogram",
        "objective": "Read a distribution and say whether it is balanced or lopsided.",
        "level": "beginner", "needs_dataset": True, "chart_type": "histogram",
    },
    "scatter_plot": {
        "title": "Relationships between two columns",
        "objective": "Read a scatter plot and describe whether two columns move together.",
        "level": "intermediate", "needs_dataset": True, "chart_type": "scatter",
    },
    "chart_interpretation": {
        "title": "Reading a chart properly",
        "objective": "State one real conclusion and one thing the chart cannot tell you.",
        "level": "beginner", "needs_dataset": True,
    },
    "grouping": {
        "title": "Grouping and summarising",
        "objective": "Split your data by a category and compare the groups.",
        "level": "beginner", "needs_dataset": True,
    },
    "trends": {
        "title": "Trends and seasonality",
        "objective": "Separate a real trend from normal month-to-month noise.",
        "level": "intermediate", "needs_dataset": True,
    },
    "correlation": {
        "title": "Correlation, and why it isn't cause",
        "objective": "Read a correlation number and resist the conclusion it invites.",
        "level": "intermediate", "needs_dataset": True,
    },
    "segmentation": {
        "title": "Splitting your audience into segments",
        "objective": "Group records into meaningful segments and describe each one.",
        "level": "intermediate", "needs_dataset": True,
    },
    "conversion_metrics": {
        "title": "Conversion and funnel metrics",
        "objective": "Calculate a conversion rate and know which denominator you used.",
        "level": "beginner", "needs_dataset": True,
    },
    "attrition_analysis": {
        "title": "Attrition: who leaves and when",
        "objective": "Measure attrition and compare it across groups of employees.",
        "level": "beginner", "needs_dataset": True,
    },
    "feature_engineering": {
        "title": "Building better columns",
        "objective": "Derive a new column that carries more signal than the raw ones.",
        "level": "intermediate", "needs_dataset": True,
    },
    "train_test_split": {
        "title": "Why you hold data back",
        "objective": "Explain what a test set protects you from.",
        "level": "intermediate", "needs_dataset": False,
    },
    "model_basics": {
        "title": "What a model actually does",
        "objective": "Describe a model as a rule learned from examples, not magic.",
        "level": "beginner", "needs_dataset": False,
    },
    "regression_vs_classification": {
        "title": "Predicting a number vs predicting a category",
        "objective": "Look at a target column and say which kind of problem it is.",
        "level": "intermediate", "needs_dataset": True,
    },
    "model_evaluation": {
        "title": "Judging whether a model is any good",
        "objective": "Read R-squared or accuracy and say what it does and doesn't prove.",
        "level": "intermediate", "needs_dataset": True,
    },
    "model_selection": {
        "title": "Choosing between models",
        "objective": "Explain why a more complex model isn't automatically a better one.",
        "level": "advanced", "needs_dataset": True,
    },
    "overfitting": {
        "title": "Overfitting: when a model memorises",
        "objective": "Spot a model that looks great on old data and fails on new data.",
        "level": "intermediate", "needs_dataset": False,
    },
    "feature_importance": {
        "title": "Which columns actually drove the prediction",
        "objective": "Rank the columns by influence and sanity-check the ranking.",
        "level": "intermediate", "needs_dataset": True,
    },
    "business_translation": {
        "title": "Turning a finding into a decision",
        "objective": "Convert one number from your analysis into an action someone can take.",
        "level": "beginner", "needs_dataset": True,
    },
}

# ------------------------------------------------------------------ goal spines

GOAL_SPINES: dict[str, list[str]] = {
    "understand_dataset": [
        "rows_and_columns", "column_meanings", "data_types", "descriptive_stats",
        "grouping", "bar_chart", "chart_interpretation", "business_translation",
    ],
    "visualization": [
        "rows_and_columns", "column_meanings", "descriptive_stats",
        "bar_chart", "line_chart", "histogram", "scatter_plot",
        "chart_interpretation", "business_translation",
    ],
    "data_cleaning": [
        "rows_and_columns", "data_types", "missing_values", "duplicates",
        "inconsistent_categories", "formatting_errors", "outliers",
        "cleaning_decisions", "business_translation",
    ],
    "eda": [
        "rows_and_columns", "column_meanings", "data_types", "descriptive_stats",
        "grouping", "histogram", "outliers", "correlation",
        "chart_interpretation", "business_translation",
    ],
    "feature_engineering": [
        "column_meanings", "data_types", "descriptive_stats", "correlation",
        "feature_engineering", "feature_importance", "business_translation",
    ],
    "machine_learning": [
        "rows_and_columns", "data_types", "descriptive_stats", "missing_values",
        "model_basics", "regression_vs_classification", "train_test_split",
        "model_evaluation", "overfitting", "model_selection", "feature_importance",
    ],
    "prediction": [
        "column_meanings", "descriptive_stats", "correlation", "model_basics",
        "regression_vs_classification", "train_test_split", "model_evaluation",
        "overfitting", "feature_importance", "business_translation",
    ],
    "business_decisions": [
        "rows_and_columns", "column_meanings", "descriptive_stats", "grouping",
        "bar_chart", "trends", "chart_interpretation", "business_translation",
    ],
}

# ------------------------------------------------------------------ role flavour

ROLE_PROFILES: dict[str, dict] = {
    "sales": {
        "description": "a sales professional",
        "priority_concepts": ["grouping", "bar_chart", "trends"],
        "vocabulary": {"category": "region", "metric": "deal value", "record": "deal"},
        "examples": "sales by region, deal size over time, which rep closes most",
    },
    "marketing": {
        "description": "a marketing professional",
        "priority_concepts": ["conversion_metrics", "segmentation", "trends", "bar_chart"],
        "vocabulary": {"category": "campaign", "metric": "conversion rate", "record": "customer"},
        "examples": "campaign performance, customer segments, conversion by channel",
    },
    "hr": {
        "description": "an HR professional",
        "priority_concepts": ["attrition_analysis", "grouping", "bar_chart"],
        "vocabulary": {"category": "department", "metric": "attrition rate", "record": "employee"},
        "examples": "attrition by department, headcount over time, performance spread",
    },
    "operations": {
        "description": "an operations professional",
        "priority_concepts": ["trends", "outliers", "grouping"],
        "vocabulary": {"category": "site", "metric": "throughput", "record": "shipment"},
        "examples": "throughput by site, delivery delays, seasonal demand",
    },
    "finance": {
        "description": "a finance professional",
        "priority_concepts": ["trends", "descriptive_stats", "outliers"],
        "vocabulary": {"category": "cost centre", "metric": "spend", "record": "transaction"},
        "examples": "spend by cost centre, budget variance, monthly revenue trend",
    },
    "data_cleaner": {
        "description": "someone who works with messy data day to day",
        "priority_concepts": ["missing_values", "duplicates", "inconsistent_categories",
                              "formatting_errors", "outliers", "cleaning_decisions"],
        "vocabulary": {"category": "category", "metric": "value", "record": "record"},
        "examples": "blank cells, duplicate rows, the same city spelled four ways",
    },
    "analyst": {
        "description": "an analyst",
        "priority_concepts": ["correlation", "grouping", "model_evaluation"],
        "vocabulary": {"category": "segment", "metric": "measure", "record": "record"},
        "examples": "segment comparisons, drivers of a metric, model quality",
    },
    "student": {
        "description": "a student learning data science",
        "priority_concepts": ["rows_and_columns", "descriptive_stats", "chart_interpretation"],
        "vocabulary": {"category": "category", "metric": "value", "record": "row"},
        "examples": "worked examples you can reproduce yourself",
    },
    "general": {
        "description": "someone new to working with data",
        "priority_concepts": ["rows_and_columns", "descriptive_stats", "bar_chart"],
        "vocabulary": {"category": "category", "metric": "value", "record": "row"},
        "examples": "simple comparisons and clear charts",
    },
}

LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}

# What an advanced learner gets appended once the spine is exhausted, so the
# path doesn't just end early for someone who already knows the basics.
ADVANCED_EXTENSIONS: dict[str, list[str]] = {
    "visualization": ["scatter_plot", "correlation", "trends"],
    "data_cleaning": ["outliers", "feature_engineering", "cleaning_decisions"],
    "understand_dataset": ["correlation", "trends", "segmentation"],
    "eda": ["feature_engineering", "segmentation"],
    "machine_learning": ["model_selection", "feature_importance"],
    "prediction": ["model_selection", "feature_importance"],
    "feature_engineering": ["model_evaluation", "overfitting"],
    "business_decisions": ["segmentation", "correlation"],
}

MAX_LESSONS = 9


def role_description(profile: UserProfile) -> str:
    role = ROLE_PROFILES.get(profile.role, ROLE_PROFILES["general"])
    return role["description"]


def role_vocabulary(role: str) -> dict:
    return ROLE_PROFILES.get(role, ROLE_PROFILES["general"])["vocabulary"]


def _visible_at_level(concept_key: str, level: str) -> bool:
    """
    A concept is skipped only if it is strictly below the learner's level --
    that's what stops an advanced learner being asked "what is a row?".
    Beginner-level concepts stay visible to an intermediate learner because
    the platform still needs to ground them in the learner's own data.
    """
    concept_level = CONCEPTS[concept_key]["level"]
    learner = LEVEL_ORDER.get(level, 0)
    if learner == 0:
        return LEVEL_ORDER[concept_level] == 0
    if learner == 1:
        return LEVEL_ORDER[concept_level] <= 1
    return LEVEL_ORDER[concept_level] >= 1   # advanced: drop the absolute basics


def build_learning_path(profile: UserProfile, analysis: dict | None = None) -> LearningPath:
    """
    The deterministic curriculum. `analysis` is the user's real dataset summary
    when one has been uploaded -- it is used only to DROP lessons the data
    cannot support (no date column means no line-chart lesson), never to invent
    new ones. A learner without a dataset still gets the full conceptual path.
    """
    goal = profile.learning_goal if profile.learning_goal in GOAL_SPINES else "understand_dataset"
    level = profile.experience_level if profile.experience_level in LEVEL_ORDER else "beginner"
    role_conf = ROLE_PROFILES.get(profile.role, ROLE_PROFILES["general"])

    spine = list(GOAL_SPINES[goal])

    # The role's priority concepts move to the front of the spine -- but only
    # after the orientation lessons, and keeping their own relative order.
    # Inserting them one at a time at a fixed index would reverse them, which
    # is how "outliers" ended up before "missing values" for a data cleaner.
    ORIENTATION = ("rows_and_columns", "column_meanings", "data_types")
    priorities = [c for c in role_conf["priority_concepts"] if c in CONCEPTS]

    head = [c for c in spine if c in ORIENTATION]
    rest = [c for c in spine if c not in ORIENTATION and c not in priorities]
    spine = head + priorities + rest

    if LEVEL_ORDER[level] >= 2:
        for concept in ADVANCED_EXTENSIONS.get(goal, []):
            if concept not in spine:
                spine.append(concept)

    # De-duplicate while preserving order, then filter by level.
    seen, ordered = set(), []
    for concept in spine:
        if concept in seen or concept not in CONCEPTS:
            continue
        seen.add(concept)
        if _visible_at_level(concept, level):
            ordered.append(concept)

    # An advanced filter can empty a short spine -- fall back to the unfiltered
    # spine rather than handing the learner a path with no lessons in it.
    if not ordered:
        ordered = [c for c in spine if c in CONCEPTS]

    if analysis:
        ordered = [c for c in ordered if _dataset_supports(c, analysis)]

    ordered = ordered[:MAX_LESSONS]

    lessons = []
    for i, concept_key in enumerate(ordered, start=1):
        meta = CONCEPTS[concept_key]
        lessons.append(Lesson(
            step=i,
            title=meta["title"],
            concept_key=concept_key,
            objective=meta["objective"],
            difficulty=meta["level"],
            needs_dataset=meta.get("needs_dataset", False),
            chart_type=meta.get("chart_type"),
            practice_prompt=None,
        ))

    rationale = (
        f"You said you work as {role_conf['description']} at a {level} level, and want to focus on "
        f"{goal.replace('_', ' ')}. So this path starts with {lessons[0].title.lower() if lessons else 'the basics'} "
        f"and builds toward {lessons[-1].title.lower() if lessons else 'applying it'}, using {role_conf['examples']} "
        f"as the running examples rather than generic textbook data."
    )

    return LearningPath(role=profile.role, experience_level=level, learning_goal=goal,
                        rationale=rationale, lessons=lessons)


def _dataset_supports(concept_key: str, analysis: dict) -> bool:
    """
    Drops lessons the learner's actual file cannot demonstrate. Teaching a
    line chart to someone whose data has no date column would mean falling
    back to a made-up example, which is exactly what this platform is meant
    to avoid.
    """
    columns = analysis.get("columns") or []
    dtypes = analysis.get("dtypes") or {}
    if not columns:
        return True

    numeric = [c for c, t in dtypes.items() if "int" in t or "float" in t]
    datetime_cols = [c for c, t in dtypes.items() if "datetime" in t]
    categorical = [c for c, t in dtypes.items() if c not in numeric and c not in datetime_cols]

    if concept_key in ("line_chart", "trends") and not datetime_cols:
        return False
    if concept_key in ("histogram", "descriptive_stats", "outliers") and not numeric:
        return False
    if concept_key == "scatter_plot" and len(numeric) < 2:
        return False
    if concept_key == "correlation" and len(numeric) < 2:
        return False
    if concept_key in ("bar_chart", "grouping", "segmentation") and not categorical:
        return False
    return True
