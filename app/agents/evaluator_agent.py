"""
EVALUATOR AGENT

Responsibility: judge a learner's free-text answer, decide what to do next,
and record what they are weak and strong at.

The score is computed in Python -- keyword coverage against what the challenge
declared a correct answer must contain. That matters for two reasons: a
learner's record has to be reproducible, and an LLM asked to grade will drift
between generous and harsh across sessions. The LLM only writes the feedback
sentence, and it is told the score rather than asked for one.

The next-difficulty decision is what closes the adaptive loop: a strong answer
raises difficulty, a weak one lowers it and pushes the concept into weak_topics
so the curriculum agent brings it back.
"""

from __future__ import annotations

import re

from app.agents.base import Agent
from app.core.schemas import AgentResponse, Challenge, EvaluationResult
from app.core.state import get_store
from app.llm.prompts import EVALUATOR_SYSTEM, EVALUATOR_USER

PASS_THRESHOLD = 0.5      # at or above this the concept counts as understood
STRONG_THRESHOLD = 0.8    # at or above this the next task gets harder
MIN_ANSWER_WORDS = 3      # below this it isn't an attempt, whatever words it contains


class EvaluatorAgent(Agent):
    name = "evaluator_agent"
    responsibility = "Score a learner's answer deterministically, give feedback, and update weak/strong topics."

    def __init__(self, store=None) -> None:
        super().__init__()
        self.store = store or get_store()

    # ------------------------------------------------------------------ scoring

    @staticmethod
    def _normalise(text: str) -> str:
        return re.sub(r"[^a-z0-9\s_]", " ", text.lower())

    def score_answer(self, answer: str, expected_keywords: list[str]) -> tuple[float, list[str], list[str]]:
        """
        Fraction of the expected ideas the answer covers.

        A keyword matches if it appears with underscores or with spaces, so a
        learner who writes "deal value" is credited for 'deal_value' -- marking
        them wrong on punctuation would be marking them on the wrong thing.
        """
        if not expected_keywords:
            # Nothing declared to look for: credit any genuine attempt rather
            # than scoring 0 on a challenge that never said what it wanted.
            return (1.0 if len(answer.split()) >= MIN_ANSWER_WORDS else 0.0), [], []

        normalised = self._normalise(answer)
        spaced = normalised.replace("_", " ")

        matched, missed = [], []
        for keyword in expected_keywords:
            key = self._normalise(keyword).strip()
            if not key:
                continue
            if key in normalised or key.replace("_", " ") in spaced:
                matched.append(keyword)
            else:
                missed.append(keyword)

        total = len(matched) + len(missed)
        return (len(matched) / total if total else 0.0), matched, missed

    def _next_difficulty(self, score: float) -> str:
        if score >= STRONG_THRESHOLD:
            return "harder"
        if score < PASS_THRESHOLD:
            return "easier"
        return "same"

    def _feedback(self, prompt: str, answer: str, score: float,
                  matched: list[str], missed: list[str]) -> tuple[str, bool]:
        if score >= STRONG_THRESHOLD:
            deterministic = ("That covers it well -- you picked up "
                             f"{', '.join(matched[:3])}. Ready for something harder.")
        elif score >= PASS_THRESHOLD:
            deterministic = (f"Good -- you got {', '.join(matched[:3])}. "
                             f"The piece worth adding is {missed[0] if missed else 'a bit more detail'}.")
        elif matched:
            deterministic = (f"You're partway there with {matched[0]}. "
                             f"Have another look at {', '.join(missed[:2])} before moving on.")
        else:
            deterministic = ("That's not quite it yet -- the answer wanted you to touch on "
                             f"{', '.join(missed[:3])}. Let's go over it again.")

        if not self.llm_enabled:
            return deterministic, False

        text = self.llm.complete(
            EVALUATOR_SYSTEM,
            EVALUATOR_USER.format(prompt=prompt, answer=answer,
                                  matched=", ".join(matched) or "none",
                                  missed=", ".join(missed) or "none",
                                  score=round(score, 2)),
            max_tokens=300,
        )
        return (text, True) if text else (deterministic, False)

    # ------------------------------------------------------------------ evaluation

    def evaluate(self, challenge: Challenge, answer: str) -> EvaluationResult:
        if len(answer.split()) < MIN_ANSWER_WORDS:
            return EvaluationResult(
                correct=False, score=0.0,
                feedback="That's a bit short to tell whether it landed -- give me a sentence or two.",
                matched=[], missed=challenge.expected_keywords, next_difficulty="easier")

        score, matched, missed = self.score_answer(answer, challenge.expected_keywords)
        feedback, used_llm = self._feedback(challenge.prompt, answer, score, matched, missed)

        result = EvaluationResult(
            correct=score >= PASS_THRESHOLD, score=round(score, 2), feedback=feedback,
            matched=matched, missed=missed, next_difficulty=self._next_difficulty(score))
        result_used_llm = used_llm
        self._last_used_llm = result_used_llm
        return result

    # ------------------------------------------------------------------ memory

    def record(self, user_id: str, concept_key: str, result: EvaluationResult,
               kind: str = "challenge") -> None:
        """
        Writes the outcome into the learner's record. A concept moves between
        weak and strong rather than accumulating in both, so the curriculum
        agent never re-teaches something the learner has since got right.
        """
        progress = self.store.get_progress(user_id)
        entry = {"concept": concept_key, "score": result.score, "correct": result.correct}

        if kind == "quiz":
            progress.quiz_scores.append(entry)
        else:
            progress.challenge_scores.append(entry)

        if result.correct:
            if concept_key in progress.weak_topics:
                progress.weak_topics.remove(concept_key)
            if concept_key not in progress.strong_topics:
                progress.strong_topics.append(concept_key)
        else:
            if concept_key in progress.strong_topics:
                progress.strong_topics.remove(concept_key)
            if concept_key not in progress.weak_topics:
                progress.weak_topics.append(concept_key)

        self.store.put_progress(user_id, progress)

    def run(self, challenge: Challenge | None = None, answer: str = "",
            user_id: str = "demo_user", record: bool = True, **kwargs) -> AgentResponse:
        if challenge is None:
            return self._respond("evaluate", "There's no challenge open to mark.", {})

        self._last_used_llm = False
        result = self.evaluate(challenge, answer)
        if record:
            self.record(user_id, challenge.concept_key, result)

        return self._respond("evaluate", result.feedback,
                             {"evaluation": result.to_dict(), "concept_key": challenge.concept_key},
                             used_llm=getattr(self, "_last_used_llm", False))
