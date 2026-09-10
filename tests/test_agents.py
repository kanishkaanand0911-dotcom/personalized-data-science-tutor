"""
Tests for the multi-agent layer: routing, dataset analysis, quiz marking,
challenge scoring, gamification and end-to-end orchestration.

Everything runs offline. Each test that persists anything gets its own
temporary state directory, so tests cannot see each other's XP.
"""

import pandas as pd
import pytest

from app.agents.data_agent import DataAgent, pick_chart_columns
from app.agents.evaluator_agent import EvaluatorAgent
from app.agents.gamification_agent import GamificationAgent
from app.agents.orchestrator import Orchestrator
from app.agents.practice_agent import PracticeAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teacher_agent import TeacherAgent
from app.agents.visualization_agent import VisualizationAgent
from app.core.schemas import Challenge, Lesson, UserProfile
from app.core.state import StateStore, level_for_xp


@pytest.fixture
def store(tmp_path):
    return StateStore(str(tmp_path / "state"))


@pytest.fixture
def orchestrator(store):
    return Orchestrator(store=store)


@pytest.fixture(scope="module")
def messy_df():
    return pd.read_csv("data/messy_sales_dataset.csv")


@pytest.fixture(scope="module")
def analysis(messy_df):
    """The full analysis, computed once -- it runs the cleaning and model
    selection loops, which are too slow to repeat per test."""
    return DataAgent().analyze(messy_df, target_col="deal_value").to_dict()


# ---------------------------------------------------------------- routing

@pytest.mark.parametrize("text,expected", [
    ("I work in sales and I'm a beginner", "onboard"),
    ("teach me the next lesson", "learn"),
    ("show me a bar chart of region", "visualize"),
    ("quiz me on that", "quiz"),
    ("give me a challenge", "practice"),
    ("how am I doing", "progress"),
    ("what's in my dataset", "analyze_data"),
])
def test_orchestrator_routes_intent(orchestrator, text, expected):
    intent, _reason, _used_llm = orchestrator.classify(text)
    assert intent == expected


def test_orchestrator_registers_all_nine_specialists(orchestrator):
    registry = orchestrator.agent_registry()
    assert len(registry) == 9
    assert all(a["responsibility"] for a in registry), "every agent must declare its responsibility"


# ---------------------------------------------------------------- data agent

def test_data_agent_reuses_the_original_cleaning_loop(analysis):
    """The data agent must not reimplement cleaning -- it should surface the
    original loop's log, backtracked attempts included."""
    log = analysis["cleaning_log"]
    assert log, "expected the original agentic cleaning loop to have run"
    assert any(not e["passed"] for e in log), "expected at least one rejected attempt (the backtrack)"
    assert any(e["passed"] for e in log)


def test_data_agent_detects_issues_and_domain(analysis):
    assert analysis["n_rows"] == 350
    assert analysis["suggested_domain"] == "sales"
    issue_types = {i["issue_type"] for i in analysis["issues"]}
    assert "missing_numeric" in issue_types
    assert "label_inconsistency" in issue_types


def test_data_agent_runs_model_selection(analysis):
    modeling = analysis["modeling"]
    assert modeling.get("chosen_model_name"), "a regression model should have been selected"
    assert modeling["chosen_model_eval"]["cv_r2_mean"] is not None


def test_chart_columns_exclude_ids(messy_df):
    """Regression: record_id was being offered as the histogram column."""
    picked = pick_chart_columns(messy_df)
    assert "record_id" not in picked["numeric"]
    assert "record_id" not in picked["categorical"]


def test_column_stats_reflect_the_cleaned_data(analysis):
    """'city' has 20 raw spellings and 5 real values -- teaching the raw count
    after the cleaning lesson would contradict it."""
    assert analysis["raw_column_stats"]["city"]["unique_count"] == 20
    assert analysis["column_stats"]["city"]["unique_count"] == 5


# ---------------------------------------------------------------- teacher

def test_teacher_grounds_the_lesson_in_real_numbers(analysis):
    lesson = Lesson(step=1, title="Rows and columns", concept_key="rows_and_columns",
                    objective="Read a table")
    block = TeacherAgent().teach(lesson, UserProfile(role="sales"), analysis)
    assert "350" in block.example, "the lesson must use the learner's real row count"
    assert block.grounded_facts


def test_teacher_adapts_language_to_the_role(analysis):
    lesson = Lesson(step=1, title="Rows and columns", concept_key="rows_and_columns",
                    objective="Read a table")
    teacher = TeacherAgent()
    sales = teacher.teach(lesson, UserProfile(role="sales"), analysis).explanation
    hr = teacher.teach(lesson, UserProfile(role="hr"), analysis).explanation
    assert sales != hr
    assert "deal" in sales


def test_teacher_always_ends_with_a_question(analysis):
    """The brief was explicit that teaching must not be a lecture dump."""
    teacher = TeacherAgent()
    for concept in ("rows_and_columns", "missing_values", "bar_chart", "correlation", "overfitting"):
        lesson = Lesson(step=1, title=concept, concept_key=concept, objective="x")
        block = teacher.teach(lesson, UserProfile(role="sales"), analysis)
        assert block.check_question.strip().endswith("?")


def test_teacher_works_without_a_dataset():
    lesson = Lesson(step=1, title="Rows and columns", concept_key="rows_and_columns", objective="x")
    block = TeacherAgent().teach(lesson, UserProfile(role="sales"), analysis=None)
    assert block.explanation
    assert "haven't uploaded" in block.example


# ---------------------------------------------------------------- visualization

@pytest.mark.parametrize("question,expected_type", [
    ("compare deal value across region", "bar"),
    ("how has deal value changed over time", "line"),
    ("what is the distribution of deal value", "histogram"),
    ("is deal value related to revenue", "scatter"),
])
def test_visualization_picks_the_right_chart(analysis, question, expected_type):
    recommendation = VisualizationAgent().recommend(question, analysis)
    assert recommendation["chart_type"] == expected_type


def test_visualization_honours_the_column_the_learner_named(analysis):
    """Regression: every bar opportunity shares the same y column, so matching
    on y alone always returned whichever came first."""
    recommendation = VisualizationAgent().recommend("compare deal value by city", analysis)
    assert recommendation["x"] == "city"


def test_visualization_renders_a_real_chart(analysis, messy_df, tmp_path):
    from app.agent.loop import run_agent
    cleaned, _ = run_agent(messy_df, verbose=False)
    response = VisualizationAgent().run(question="compare deal value across region",
                                        analysis=analysis, df=cleaned, profile=UserProfile(role="sales"))
    rendered = response.data["rendered"]
    assert rendered.get("path", "").endswith(".png")
    assert rendered["data"], "the chart must carry the real aggregated values"


# ---------------------------------------------------------------- quiz

def test_quiz_marking_is_deterministic():
    agent = QuizAgent()
    question = agent.generate("bar_chart", UserProfile(role="sales"), shuffle=False)
    assert agent.mark(question, question.correct_index)["correct"] is True
    assert agent.mark(question, (question.correct_index + 1) % len(question.options))["correct"] is False


def test_quiz_options_are_shuffled():
    """Without shuffling, "always pick option 0" would score 100%."""
    agent = QuizAgent()
    positions = {agent.generate("bar_chart", UserProfile()).correct_index for _ in range(30)}
    assert len(positions) > 1


def test_quiz_covers_every_concept_in_the_curriculum():
    from app.personalization.learning_path import CONCEPTS
    from app.agents.quiz_agent import QUESTION_BANK
    missing = set(CONCEPTS) - set(QUESTION_BANK)
    assert not missing, f"no quiz question for: {sorted(missing)}"


# ---------------------------------------------------------------- practice + evaluator

def test_practice_task_names_real_columns(analysis):
    challenge = PracticeAgent().build("bar_chart", UserProfile(role="sales"), analysis)
    assert "deal_value" in challenge.prompt
    assert challenge.expected_keywords


def test_practice_difficulty_scales_with_level(analysis):
    agent = PracticeAgent()
    beginner = agent.build("correlation", UserProfile(experience_level="beginner"), analysis)
    advanced = agent.build("correlation", UserProfile(experience_level="advanced"), analysis)
    assert len(advanced.prompt) > len(beginner.prompt)


def test_evaluator_scores_by_keyword_coverage(store):
    agent = EvaluatorAgent(store)
    challenge = Challenge(prompt="Compare deal_value across region", concept_key="bar_chart",
                          expected_keywords=["bar", "region", "deal_value", "highest"])

    strong = agent.evaluate(challenge, "I built a bar chart of region against deal value and East was highest")
    weak = agent.evaluate(challenge, "I looked at the numbers and they seemed fine to me")

    assert strong.correct and strong.score > weak.score
    assert not weak.correct
    assert strong.next_difficulty == "harder"
    assert weak.next_difficulty == "easier"


def test_evaluator_credits_spaces_for_underscored_columns(store):
    """A learner writing "deal value" must not be marked down for punctuation."""
    challenge = Challenge(prompt="x", concept_key="bar_chart", expected_keywords=["deal_value"])
    assert EvaluatorAgent(store).evaluate(challenge, "I charted the deal value column").score == 1.0


def test_evaluator_rejects_a_non_answer(store):
    challenge = Challenge(prompt="x", concept_key="bar_chart", expected_keywords=["bar"])
    assert EvaluatorAgent(store).evaluate(challenge, "ok").score == 0.0


def test_evaluator_updates_weak_and_strong_topics(store):
    agent = EvaluatorAgent(store)
    challenge = Challenge(prompt="x", concept_key="bar_chart", expected_keywords=["bar", "region"])

    agent.record("u", "bar_chart", agent.evaluate(challenge, "no idea what to do here at all"))
    assert "bar_chart" in store.get_progress("u").weak_topics

    # Getting it right later must clear it, not leave it in both lists.
    agent.record("u", "bar_chart", agent.evaluate(challenge, "a bar chart split by region"))
    progress = store.get_progress("u")
    assert "bar_chart" in progress.strong_topics
    assert "bar_chart" not in progress.weak_topics


# ---------------------------------------------------------------- gamification

def test_xp_awards_and_levelling(store):
    agent = GamificationAgent(store)
    assert agent.award("u", "lesson_completed")["xp_awarded"] == 10
    assert agent.award("u", "quiz_correct")["xp_awarded"] == 20
    assert store.get_progress("u").xp == 30
    assert agent.summary("u")["level"] == level_for_xp(30)


def test_wrong_quiz_answer_still_earns_something(store):
    """Attempting is the behaviour to reward; zero XP for a wrong answer
    punishes trying."""
    assert GamificationAgent(store).award("u", "quiz_incorrect")["xp_awarded"] > 0


def test_badges_are_awarded_once(store):
    agent = GamificationAgent(store)
    first = agent.award("u", "dataset_analyzed")
    second = agent.award("u", "dataset_analyzed")
    assert "Data Explorer" in first["new_badges"]
    assert "Data Explorer" not in second["new_badges"]
    assert second["all_badges"].count("Data Explorer") == 1


def test_original_gamification_rules_still_apply(store):
    """The original project's badge rules must survive -- Detective's Eye is
    the badge for a case where the agent had to backtrack."""
    cases = [{"id": "deal_value", "kind": "cleaning", "concept": "Handling missing data",
              "title": "The case of the missing deal value entries", "resolved": True, "had_retry": True}]
    result = GamificationAgent(store).badges_for_cleaning_cases(cases)
    assert "Detective's Eye" in result["case_badges"].values()
    assert result["final_badge"] == "Case Closed"


# ---------------------------------------------------------------- orchestration

def test_full_learner_journey(orchestrator, messy_df):
    user = "journey_user"

    onboard = orchestrator.chat(user, "I work in sales, I'm a complete beginner, "
                                       "I want to learn to visualize my sales data")
    assert onboard.intent == "onboard"
    assert onboard.profile["role"] == "sales"
    assert "profiler_agent" in onboard.agents_called

    uploaded = orchestrator.upload_dataset(user, messy_df, target_col="deal_value")
    assert "data_agent" in uploaded.agents_called
    assert "curriculum_agent" in uploaded.agents_called

    lesson = orchestrator.next_lesson(user)
    assert {"teacher_agent", "quiz_agent", "practice_agent"} <= set(lesson.agents_called)
    assert lesson.progress["lessons_completed"] == 1
    assert lesson.progress["xp"] > 0

    quiz = next(r["data"]["quiz"] for r in lesson.responses if r["agent"] == "quiz_agent")
    marked = orchestrator.answer_quiz(user, quiz, quiz["correct_index"])
    assert marked.progress["quizzes_correct"] == 1

    # The second lesson must be a different one -- the learner has to advance.
    second = orchestrator.next_lesson(user)
    assert second.progress["current_step"] == 3


def test_two_roles_get_different_paths_from_the_same_dataset(orchestrator, messy_df):
    orchestrator.chat("sales_u", "I work in sales, complete beginner, I want to learn visualization")
    orchestrator.chat("clean_u", "I work with messy data and want to learn data cleaning")
    orchestrator.upload_dataset("sales_u", messy_df, target_col="deal_value")
    orchestrator.upload_dataset("clean_u", messy_df, target_col="deal_value")

    def concepts(user):
        return [l["concept_key"] for l in orchestrator.store.load(user)["learning_path"]["lessons"]]

    assert concepts("sales_u") != concepts("clean_u")
    assert "bar_chart" in concepts("sales_u")
    assert "missing_values" in concepts("clean_u")


def test_progress_persists_across_orchestrator_instances(store, messy_df):
    """A learner's XP must survive a restart -- state lives in the store, not
    in the orchestrator object."""
    Orchestrator(store=store).chat("persist_u", "I work in sales and I'm a beginner")
    first_xp = store.get_progress("persist_u").xp

    fresh = Orchestrator(store=store)
    assert fresh.gamification.summary("persist_u")["xp"] == first_xp
    assert fresh._load_session("persist_u")["profile"].role == "sales"


def test_everything_works_without_an_llm(orchestrator, messy_df):
    """The core demo must not require a paid API. Every agent must report that
    it took the deterministic path when no key is configured."""
    from app.llm.llm_client import get_llm_client
    if get_llm_client().enabled:
        pytest.skip("an API key is configured, so the fallback path is not under test here")

    orchestrator.chat("offline_u", "I work in HR, beginner, I want to understand my data")
    orchestrator.upload_dataset("offline_u", messy_df, target_col="deal_value")
    lesson = orchestrator.next_lesson("offline_u")

    assert lesson.message
    assert all(not r["used_llm"] for r in lesson.responses)
