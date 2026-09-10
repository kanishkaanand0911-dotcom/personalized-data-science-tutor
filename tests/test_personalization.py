"""
Tests for the personalization engine: profile extraction, experience-level
detection and learning-path generation.

These run with no API key and never touch the network -- extract_profile is
called with use_llm=False so the deterministic rules are what is actually
under test, rather than whatever a model happened to return.
"""

import pytest

from app.core.schemas import UserProfile
from app.personalization.learning_path import build_learning_path, CONCEPTS
from app.personalization.profile_extractor import (extract_profile_rules,
                                                    next_onboarding_questions)


# ---------------------------------------------------------------- extraction

@pytest.mark.parametrize("text,expected_role", [
    ("I work in sales and close deals all day", "sales"),
    ("I'm in marketing, I run campaigns", "marketing"),
    ("I work in HR looking after our people team", "hr"),
    ("I work in operations and supply chain", "operations"),
    ("I work with messy data every day", "data_cleaner"),
    ("I am a student studying business", "student"),
])
def test_role_detection(text, expected_role):
    assert extract_profile_rules(text).role == expected_role


@pytest.mark.parametrize("text,expected_level", [
    ("I am a complete beginner", "beginner"),
    ("I have absolutely no idea about data science", "beginner"),
    ("I know the basics and have used pandas a bit", "intermediate"),
    ("I'm an experienced data scientist, pretty advanced", "advanced"),
])
def test_experience_level_detection(text, expected_level):
    assert extract_profile_rules(text).experience_level == expected_level


def test_experience_defaults_to_beginner_when_unstated():
    """An unstated level must default to beginner AND record low confidence,
    so the system asks rather than silently assuming."""
    profile = extract_profile_rules("I work in sales")
    assert profile.experience_level == "beginner"
    assert profile.confidence.get("experience_level", 0.0) < 0.5


def test_extracts_name_and_age():
    profile = extract_profile_rules("My name is Alex. I am 20 years old. I work in sales.")
    assert profile.name == "Alex"
    assert profile.age == 20


def test_does_not_mistake_experience_word_for_a_name():
    """Regression: "I'm a beginner" must not produce name="Beginner"."""
    assert extract_profile_rules("I'm a beginner at all this").name is None


def test_years_of_experience_is_not_read_as_age():
    profile = extract_profile_rules("I have 15 years of experience in marketing")
    assert profile.age is None


@pytest.mark.parametrize("text,expected", [
    ("I want to visualize my sales data", True),
    ("I have campaign data to work with", True),
    ("I don't have any data yet", False),
])
def test_dataset_availability_detection(text, expected):
    assert extract_profile_rules(text).dataset_available is expected


def test_profile_accumulates_across_turns():
    """A learner who reveals their job now and their goal later must end up
    with both, not have the second message overwrite the first."""
    profile = extract_profile_rules("I work in sales")
    profile = extract_profile_rules("I want to learn visualization", base=profile)
    assert profile.role == "sales"
    assert profile.learning_goal == "visualization"


def test_onboarding_asks_only_for_what_is_missing():
    complete = extract_profile_rules(
        "I work in sales, I'm a complete beginner, I want to learn visualization with my sales data")
    assert next_onboarding_questions(complete) == []

    vague = extract_profile_rules("hello there")
    questions = next_onboarding_questions(vague)
    assert 0 < len(questions) <= 2, "must ask something, but never a giant questionnaire"


# ---------------------------------------------------------------- learning path

def test_path_differs_by_role_for_the_same_goal():
    sales = build_learning_path(UserProfile(role="sales", experience_level="beginner",
                                             learning_goal="understand_dataset"))
    hr = build_learning_path(UserProfile(role="hr", experience_level="beginner",
                                          learning_goal="understand_dataset"))
    assert [l.concept_key for l in sales.lessons] != [l.concept_key for l in hr.lessons]
    assert "attrition_analysis" in [l.concept_key for l in hr.lessons]


def test_data_cleaner_path_prioritises_cleaning_concepts():
    path = build_learning_path(UserProfile(role="data_cleaner", experience_level="beginner",
                                            learning_goal="data_cleaning"))
    concepts = [l.concept_key for l in path.lessons]
    for expected in ("missing_values", "duplicates", "inconsistent_categories", "formatting_errors"):
        assert expected in concepts


def test_cleaning_concepts_are_taught_in_a_sensible_order():
    """Regression: role priority concepts were being inserted one at a time at
    a fixed index, which reversed them and put outliers before missing values."""
    path = build_learning_path(UserProfile(role="data_cleaner", experience_level="beginner",
                                            learning_goal="data_cleaning"))
    concepts = [l.concept_key for l in path.lessons]
    assert concepts.index("missing_values") < concepts.index("outliers")


def test_advanced_learner_skips_the_absolute_basics():
    path = build_learning_path(UserProfile(role="analyst", experience_level="advanced",
                                            learning_goal="prediction"))
    assert "rows_and_columns" not in [l.concept_key for l in path.lessons]


def test_beginner_learner_starts_with_the_basics():
    path = build_learning_path(UserProfile(role="sales", experience_level="beginner",
                                            learning_goal="visualization"))
    assert path.lessons[0].concept_key == "rows_and_columns"


def test_path_is_never_empty_and_steps_are_sequential():
    for role in ("sales", "marketing", "hr", "operations", "data_cleaner", "analyst", "student", "general"):
        for level in ("beginner", "intermediate", "advanced"):
            for goal in ("understand_dataset", "visualization", "data_cleaning", "machine_learning"):
                path = build_learning_path(UserProfile(role=role, experience_level=level,
                                                        learning_goal=goal))
                assert path.lessons, f"empty path for {role}/{level}/{goal}"
                assert [l.step for l in path.lessons] == list(range(1, len(path.lessons) + 1))
                for lesson in path.lessons:
                    assert lesson.concept_key in CONCEPTS


def test_path_drops_lessons_the_dataset_cannot_support():
    """A dataset with no date column must not be given a line-chart lesson --
    teaching it would mean falling back to an invented example."""
    no_dates = {"columns": ["region", "amount"],
                "dtypes": {"region": "object", "amount": "float64"}}
    path = build_learning_path(UserProfile(role="sales", experience_level="beginner",
                                            learning_goal="visualization"), analysis=no_dates)
    concepts = [l.concept_key for l in path.lessons]
    assert "line_chart" not in concepts
    assert "bar_chart" in concepts
