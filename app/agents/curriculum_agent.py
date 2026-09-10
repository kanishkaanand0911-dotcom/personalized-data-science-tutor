"""
CURRICULUM / LEARNING PATH AGENT

Responsibility: decide WHAT this learner should learn and in what order.

Input:  UserProfile + (optional) DatasetAnalysis + what they already got wrong
Output: a LearningPath

The sequence itself is deterministic (app.personalization.learning_path), for
a reason worth stating: a learner asking "why am I being taught this?" gets a
concrete answer -- their role, level and goal selected these concepts in this
order -- rather than "the model chose it". What the LLM may do here is only
reword the rationale.

Weak topics from the evaluator are re-inserted near the front, so a learner
who missed a quiz on missing values meets it again before moving on.
"""

from __future__ import annotations

from app.agents.base import Agent
from app.core.schemas import AgentResponse, LearningPath, Lesson, UserProfile
from app.personalization.learning_path import build_learning_path, CONCEPTS


class CurriculumAgent(Agent):
    name = "curriculum_agent"
    responsibility = "Build and adapt a personalized, ordered learning path from role, level, goal and dataset."

    def build(self, profile: UserProfile, analysis: dict | None = None,
              weak_topics: list[str] | None = None) -> LearningPath:
        path = build_learning_path(profile, analysis)

        if weak_topics:
            path = self._reinforce(path, weak_topics)

        return path

    def _reinforce(self, path: LearningPath, weak_topics: list[str]) -> LearningPath:
        """
        Move concepts the learner struggled with to the front of what's left,
        and re-label them as revision so the teacher agent knows to slow down.
        A weak topic that isn't in the path at all is added -- the learner
        demonstrably needs it.
        """
        weak = [t for t in weak_topics if t in CONCEPTS]
        if not weak:
            return path

        existing = {l.concept_key: l for l in path.lessons}
        revision, rest = [], []
        for lesson in path.lessons:
            (revision if lesson.concept_key in weak else rest).append(lesson)

        for topic in weak:
            if topic not in existing:
                meta = CONCEPTS[topic]
                revision.append(Lesson(
                    step=0, title=meta["title"], concept_key=topic,
                    objective=meta["objective"], difficulty=meta["level"],
                    needs_dataset=meta.get("needs_dataset", False),
                    chart_type=meta.get("chart_type"),
                ))

        merged = revision + rest
        for i, lesson in enumerate(merged, start=1):
            lesson.step = i

        path.lessons = merged
        path.rationale += (
            f" Two things you found tricky ({', '.join(t.replace('_', ' ') for t in weak[:2])}) "
            f"have been moved to the front so you get another go at them first."
        )
        return path

    def run(self, profile: UserProfile | None = None, analysis: dict | None = None,
            weak_topics: list[str] | None = None, **kwargs) -> AgentResponse:
        profile = profile or UserProfile()
        path = self.build(profile, analysis, weak_topics)

        lines = [path.rationale, "", f"Your path ({len(path.lessons)} lessons):"]
        lines += [f"  {l.step}. {l.title}" for l in path.lessons]

        return self._respond("learning_path", "\n".join(lines),
                             {"learning_path": path.to_dict()}, used_llm=False)
