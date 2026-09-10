"""
USER PROFILER AGENT

Responsibility: turn what a learner said about themselves into a structured
UserProfile, and say what it still needs to ask.

Input:  free text, plus the profile built up so far (profiles accumulate
        across turns -- a learner who says their job now and their goal three
        messages later ends up with both).
Output: AgentResponse whose data carries {profile, questions, newly_learned}.

It does not build a curriculum and does not teach. Deciding what to do with
the profile is the orchestrator's job.
"""

from __future__ import annotations

from app.agents.base import Agent
from app.core.schemas import AgentResponse, UserProfile
from app.personalization.profile_extractor import extract_profile, next_onboarding_questions
from app.personalization.user_profile import profile_summary_lines


class ProfilerAgent(Agent):
    name = "profiler_agent"
    responsibility = "Extract a structured learner profile from conversation and identify what is still unknown."

    def run(self, text: str = "", profile: UserProfile | None = None, **kwargs) -> AgentResponse:
        before = profile.to_dict() if profile else {}
        updated, used_llm = extract_profile(text, base=profile)

        newly_learned = [
            field for field in ("name", "age", "role", "experience_level", "learning_goal",
                                "domain", "dataset_available")
            if before.get(field) != getattr(updated, field)
        ]

        questions = next_onboarding_questions(updated)

        if questions:
            message = (
                "Here's what I've got so far:\n  "
                + "\n  ".join(profile_summary_lines(updated))
                + "\n\nA couple of quick things so I can tailor this properly:\n  - "
                + "\n  - ".join(questions)
            )
        else:
            message = (
                "Got it -- here's your profile:\n  "
                + "\n  ".join(profile_summary_lines(updated))
                + "\n\nThat's enough for me to build you a learning path."
            )

        return self._respond(
            intent="profile",
            message=message,
            data={
                "profile": updated.to_dict(),
                "questions": questions,
                "newly_learned": newly_learned,
                "profile_complete": not questions,
            },
            used_llm=used_llm,
        )
