"""
GAMIFICATION AGENT

Responsibility: award XP, levels, badges and streaks, and persist them.

It wraps the ORIGINAL app/gamification/rules.py rather than replacing it --
that module's stateless badge rules (Detective's Eye for a case that needed a
retry, Format Fixer, Model Scout, Case Closed) still apply to cleaning cases,
and its XP_RULES are still the source of truth for case/quiz XP. What this
agent adds is the learning-platform layer: lesson XP, levels, streaks, and the
badges tied to the personalized path.
"""

from __future__ import annotations

from app.agents.base import Agent
from app.core.schemas import AgentResponse
from app.core.state import Progress, get_store, level_for_xp, xp_to_next_level

# The original project's rules, preserved and reused.
from app.gamification.rules import XP_RULES as CASE_XP_RULES, badge_for_case, final_badge

# Platform XP, extending (not replacing) the original CASE_XP_RULES.
XP_EVENTS: dict[str, int] = {
    "lesson_completed": 10,
    "quiz_correct": 20,
    "quiz_incorrect": 5,        # a wrong answer still earns something -- attempting is the behaviour to reward
    "challenge_completed": 30,
    "challenge_partial": 15,
    "dataset_analyzed": 25,
    "profile_completed": 10,
    "path_created": 10,
}

# badge id -> (display name, description, predicate over progress + context)
BADGE_RULES: list[tuple[str, str, str]] = [
    ("Data Explorer", "Analysed your first dataset", "dataset_analyzed"),
    ("First Steps", "Completed your first lesson", "first_lesson"),
    ("Visualization Rookie", "Completed a chart lesson", "chart_lesson"),
    ("Cleaning Champion", "Completed three cleaning lessons", "cleaning_lessons"),
    ("Insight Hunter", "Completed a practical challenge", "challenge_done"),
    ("Model Builder", "Reached the model lessons", "model_lesson"),
    ("Quiz Master", "Answered five quizzes correctly", "quiz_master"),
    ("Streak Starter", "Came back three days running", "streak_3"),
    ("Path Finisher", "Completed every lesson on your path", "path_complete"),
]

CHART_CONCEPTS = {"bar_chart", "line_chart", "histogram", "scatter_plot", "chart_interpretation"}
CLEANING_CONCEPTS = {"missing_values", "duplicates", "inconsistent_categories",
                     "formatting_errors", "outliers", "cleaning_decisions"}
MODEL_CONCEPTS = {"model_basics", "regression_vs_classification", "train_test_split",
                  "model_evaluation", "overfitting", "model_selection", "feature_importance"}


class GamificationAgent(Agent):
    name = "gamification_agent"
    responsibility = "Award XP, levels, badges and streaks, and persist learner progress."

    def __init__(self, store=None) -> None:
        super().__init__()
        self.store = store or get_store()

    # ------------------------------------------------------------------ xp

    def award(self, user_id: str, event: str, concept_key: str | None = None,
              path_length: int | None = None) -> dict:
        """
        Applies one XP event and returns what changed. Returns the deltas
        rather than just the totals, so the UI can show "+20 XP" and
        "Level up!" rather than the learner having to spot the difference.
        """
        amount = XP_EVENTS.get(event, 0)
        progress = self.store.get_progress(user_id)

        before_level = progress.level
        progress.xp += amount
        progress.level = level_for_xp(progress.xp)

        new_badges = self._check_badges(progress, concept_key, event, path_length)
        for badge in new_badges:
            if badge not in progress.badges:
                progress.badges.append(badge)

        self.store.put_progress(user_id, progress)
        self.store.log_event(user_id, event, {"xp": amount, "concept": concept_key})

        return {
            "event": event,
            "xp_awarded": amount,
            "total_xp": progress.xp,
            "level": progress.level,
            "leveled_up": progress.level > before_level,
            "new_badges": new_badges,
            "all_badges": list(progress.badges),
            "xp_to_next_level": xp_to_next_level(progress.xp),
        }

    def _check_badges(self, progress: Progress, concept_key: str | None,
                      event: str, path_length: int | None) -> list[str]:
        earned: list[str] = []

        def add(name: str) -> None:
            if name not in progress.badges and name not in earned:
                earned.append(name)

        if event == "dataset_analyzed":
            add("Data Explorer")
        if event == "lesson_completed":
            if len(progress.completed_lessons) >= 1:
                add("First Steps")
            if concept_key in CHART_CONCEPTS:
                add("Visualization Rookie")
            if concept_key in MODEL_CONCEPTS:
                add("Model Builder")
        if event in ("challenge_completed", "challenge_partial"):
            add("Insight Hunter")

        cleaning_done = sum(1 for h in progress.history
                            if h.get("detail", {}).get("concept") in CLEANING_CONCEPTS
                            and h.get("event") == "lesson_completed")
        if cleaning_done >= 3:
            add("Cleaning Champion")

        if sum(1 for q in progress.quiz_scores if q.get("correct")) >= 5:
            add("Quiz Master")
        if progress.streak_days >= 3:
            add("Streak Starter")
        if path_length and len(progress.completed_lessons) >= path_length:
            add("Path Finisher")

        return earned

    # ------------------------------------------------------------------ original rules bridge

    def badges_for_cleaning_cases(self, cases: list[dict]) -> dict:
        """
        Applies the ORIGINAL project's badge rules to the cleaning cases the
        agentic loop produced. Kept intact so a learner working through the
        cleaning path still earns Detective's Eye when the agent had to
        backtrack -- the moment the original project was built around.
        """
        per_case = {}
        for case in cases:
            badge = badge_for_case(case)
            if badge:
                per_case[case.get("title", case.get("id", "case"))] = badge
        return {
            "case_badges": per_case,
            "final_badge": final_badge(cases),
            "case_xp_rules": CASE_XP_RULES,
        }

    # ------------------------------------------------------------------ agent api

    def summary(self, user_id: str) -> dict:
        progress = self.store.get_progress(user_id)
        correct = sum(1 for q in progress.quiz_scores if q.get("correct"))
        return {
            "xp": progress.xp,
            "level": progress.level,
            "xp_to_next_level": xp_to_next_level(progress.xp),
            "badges": progress.badges,
            "streak_days": progress.streak_days,
            "lessons_completed": len(progress.completed_lessons),
            "current_step": progress.current_step,
            "quizzes_answered": len(progress.quiz_scores),
            "quizzes_correct": correct,
            "challenges_attempted": len(progress.challenge_scores),
            "weak_topics": progress.weak_topics,
            "strong_topics": progress.strong_topics,
        }

    def run(self, user_id: str = "demo_user", event: str | None = None,
            concept_key: str | None = None, path_length: int | None = None, **kwargs) -> AgentResponse:
        if event:
            result = self.award(user_id, event, concept_key, path_length)
            message = f"+{result['xp_awarded']} XP ({result['total_xp']} total, level {result['level']})"
            if result["leveled_up"]:
                message += f" -- level up to {result['level']}!"
            if result["new_badges"]:
                message += f" Badge earned: {', '.join(result['new_badges'])}."
            return self._respond("gamification", message, result)

        s = self.summary(user_id)
        message = (f"Level {s['level']} - {s['xp']} XP ({s['xp_to_next_level']} to next level)\n"
                    f"Lessons completed: {s['lessons_completed']} | Quizzes correct: "
                    f"{s['quizzes_correct']}/{s['quizzes_answered']} | Streak: {s['streak_days']} day(s)\n"
                    f"Badges: {', '.join(s['badges']) if s['badges'] else 'none yet'}")
        return self._respond("progress", message, s)
