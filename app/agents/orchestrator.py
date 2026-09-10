"""
ORCHESTRATOR AGENT

Responsibility: understand what the learner wants and decide which specialists
to call, in what order. It coordinates; it does not teach, analyse or score.

Routing is rule-first for the same reason the curriculum is: intent
classification that a person can read and predict beats one that changes
between runs. The keyword router below handles the common phrasings; an LLM
classifier is consulted only when the rules find nothing, and its answer is
still restricted to the same fixed intent list.

The workflow per intent is explicit -- e.g. `learn` runs
profiler -> curriculum -> teacher -> quiz -> gamification -- which is what
makes this a coordinated multi-agent pipeline rather than one model deciding
everything in a single prompt.
"""

from __future__ import annotations

import pandas as pd

from app.agents.base import Agent
from app.agents.curriculum_agent import CurriculumAgent
from app.agents.data_agent import DataAgent
from app.agents.evaluator_agent import EvaluatorAgent
from app.agents.gamification_agent import GamificationAgent
from app.agents.practice_agent import PracticeAgent
from app.agents.profiler_agent import ProfilerAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teacher_agent import TeacherAgent
from app.agents.visualization_agent import VisualizationAgent
from app.core.schemas import (AgentResponse, Challenge, DatasetAnalysis, Lesson,
                              OrchestratorResult, UserProfile)
from app.core.state import get_store
from app.llm.prompts import ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER
from app.personalization.user_profile import save_profile

INTENTS = ("onboard", "analyze_data", "learn", "visualize", "quiz", "practice", "progress", "question")

INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "progress": ("my progress", "how am i doing", "my xp", "my level", "my badges",
                 "how far", "my streak", "score so far"),
    "quiz": ("quiz me", "test me", "ask me a question", "quiz", "check my understanding"),
    "practice": ("give me a challenge", "practice", "exercise", "task", "let me try", "challenge me"),
    "visualize": ("chart", "graph", "plot", "visuali", "show me a bar", "which chart", "dashboard"),
    "analyze_data": ("analyse my data", "analyze my data", "what's in my data", "look at my data",
                     "my dataset", "describe my data", "data quality", "what's wrong with my data"),
    "learn": ("teach me", "next lesson", "start learning", "continue", "lesson", "explain",
              "what should i learn", "learning path", "curriculum", "next step"),
    "onboard": ("i work", "i am a", "i'm a", "my name is", "my role", "i want to learn",
                "i study", "i'm new", "beginner", "years old"),
}


class Orchestrator(Agent):
    name = "orchestrator"
    responsibility = "Classify learner intent, route to the right specialist agents, and assemble the response."

    def __init__(self, store=None) -> None:
        super().__init__()
        self.store = store or get_store()
        self.profiler = ProfilerAgent()
        self.data_agent = DataAgent()
        self.curriculum = CurriculumAgent()
        self.teacher = TeacherAgent()
        self.visualization = VisualizationAgent()
        self.quiz = QuizAgent()
        self.practice = PracticeAgent()
        self.gamification = GamificationAgent(self.store)
        self.evaluator = EvaluatorAgent(self.store)

    # ------------------------------------------------------------------ routing

    def classify(self, text: str) -> tuple[str, str, bool]:
        """Returns (intent, reason, used_llm)."""
        lowered = " " + text.lower().strip() + " "

        best_intent, best_len = None, 0
        for intent, keywords in INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in lowered and len(keyword) > best_len:
                    best_intent, best_len = intent, len(keyword)
        if best_intent:
            return best_intent, f"matched the phrase pattern for '{best_intent}'", False

        if self.llm_enabled:
            parsed = self.llm.complete_json(ORCHESTRATOR_SYSTEM,
                                            ORCHESTRATOR_USER.format(text=text), max_tokens=200)
            if isinstance(parsed, dict) and parsed.get("intent") in INTENTS:
                return parsed["intent"], str(parsed.get("reason", "classified by model")), True

        return "question", "no specific intent matched", False

    # ------------------------------------------------------------------ session helpers

    def _load_session(self, user_id: str) -> dict:
        state = self.store.load(user_id)
        return {
            "profile": UserProfile.from_dict(state["profile"]) if state.get("profile")
                        else UserProfile(user_id=user_id),
            "analysis": state.get("dataset_analysis"),
            "path": state.get("learning_path"),
            "progress": self.store.get_progress(user_id),
        }

    def _current_lesson(self, path_dict: dict | None, step: int) -> Lesson | None:
        if not path_dict:
            return None
        for raw in path_dict.get("lessons", []):
            if raw["step"] == step:
                return Lesson(**raw)
        return None

    def _ensure_path(self, user_id: str, profile: UserProfile, analysis: dict | None,
                     responses: list[AgentResponse]) -> dict:
        """Builds a path if the learner doesn't have one yet, reusing weak
        topics so a returning learner gets reinforcement, not a reset."""
        session = self._load_session(user_id)
        if session["path"]:
            return session["path"]

        response = self.curriculum.run(profile=profile, analysis=analysis,
                                        weak_topics=session["progress"].weak_topics)
        responses.append(response)
        path = response.data["learning_path"]
        self.store.update(user_id, learning_path=path)
        self.gamification.award(user_id, "path_created")
        return path

    # ------------------------------------------------------------------ public api

    def onboard(self, user_id: str, text: str) -> OrchestratorResult:
        """profiler -> (curriculum, once the profile is complete)"""
        responses: list[AgentResponse] = []
        session = self._load_session(user_id)

        profile_response = self.profiler.run(text=text, profile=session["profile"])
        responses.append(profile_response)
        profile = UserProfile.from_dict(profile_response.data["profile"])
        save_profile(user_id, profile, self.store)

        questions = profile_response.data["questions"]
        message = profile_response.message

        if profile_response.data["profile_complete"]:
            self.gamification.award(user_id, "profile_completed")
            # A path built now is rebuilt after a dataset arrives, since the
            # dataset can rule lessons out.
            path_response = self.curriculum.run(profile=profile, analysis=session["analysis"],
                                                 weak_topics=session["progress"].weak_topics)
            responses.append(path_response)
            self.store.update(user_id, learning_path=path_response.data["learning_path"])
            message += "\n\n" + path_response.message

        return self._assemble(user_id, "onboard", message, responses, questions)

    def upload_dataset(self, user_id: str, df: pd.DataFrame, target_col: str | None = None) -> OrchestratorResult:
        """data_agent -> curriculum (rebuilt against what the data supports) -> gamification"""
        responses: list[AgentResponse] = []
        session = self._load_session(user_id)

        data_response = self.data_agent.run(df=df, target_col=target_col)
        responses.append(data_response)
        analysis = data_response.data["analysis"]

        profile = session["profile"]
        if analysis and analysis.get("suggested_domain") and not profile.domain:
            profile.domain = analysis["suggested_domain"]
        profile.dataset_available = True
        profile.dataset_type = analysis.get("suggested_domain") if analysis else None
        save_profile(user_id, profile, self.store)

        self.store.update(user_id, dataset_analysis=analysis)

        # The path is rebuilt, not patched: a dataset with no date column must
        # drop the line-chart lesson rather than teach it against nothing.
        path_response = self.curriculum.run(profile=profile, analysis=analysis,
                                             weak_topics=session["progress"].weak_topics)
        responses.append(path_response)
        self.store.update(user_id, learning_path=path_response.data["learning_path"])

        award = self.gamification.award(user_id, "dataset_analyzed")
        message = data_response.message + "\n\n" + path_response.message
        if award["new_badges"]:
            message += f"\n\nBadge earned: {', '.join(award['new_badges'])}."

        return self._assemble(user_id, "analyze_data", message, responses)

    def next_lesson(self, user_id: str, df: pd.DataFrame | None = None) -> OrchestratorResult:
        """curriculum -> teacher -> visualization (chart lessons) -> quiz -> practice"""
        responses: list[AgentResponse] = []
        session = self._load_session(user_id)
        profile, analysis = session["profile"], session["analysis"]

        path = self._ensure_path(user_id, profile, analysis, responses)
        step = session["progress"].current_step
        lesson = self._current_lesson(path, step)

        if lesson is None:
            return self._assemble(user_id, "learn",
                                   "You've finished every lesson on your path. Upload new data or "
                                   "tell me a new goal and I'll build you another one.", responses)

        teach_response = self.teacher.run(lesson=lesson, profile=profile, analysis=analysis)
        responses.append(teach_response)
        message = teach_response.message

        # A chart lesson gets the actual chart rendered alongside it.
        if lesson.chart_type and analysis:
            viz_response = self.visualization.run(question=lesson.title, analysis=analysis, df=df,
                                                   profile=profile, chart_type=lesson.chart_type)
            responses.append(viz_response)
            message += "\n\n" + viz_response.message

        facts = teach_response.data.get("teaching_block", {}).get("grounded_facts", [])
        quiz_response = self.quiz.run(concept_key=lesson.concept_key, profile=profile, facts=facts)
        responses.append(quiz_response)
        message += "\n\nQuick check -- " + quiz_response.message

        practice_response = self.practice.run(concept_key=lesson.concept_key, profile=profile,
                                               analysis=analysis)
        responses.append(practice_response)
        message += "\n\n" + practice_response.message

        # The lesson counts as delivered here; the quiz and challenge earn
        # their own XP when the learner actually answers them.
        progress = self.store.get_progress(user_id)
        if lesson.step not in progress.completed_lessons:
            progress.completed_lessons.append(lesson.step)
        progress.current_step = lesson.step + 1
        self.store.put_progress(user_id, progress)

        award = self.gamification.award(user_id, "lesson_completed", lesson.concept_key,
                                         path_length=len(path.get("lessons", [])))
        message += f"\n\n{award['xp_awarded']} XP earned ({award['total_xp']} total, level {award['level']})."
        if award["new_badges"]:
            message += f" Badge earned: {', '.join(award['new_badges'])}."

        return self._assemble(user_id, "learn", message, responses)

    def answer_quiz(self, user_id: str, quiz: dict, answer_index: int) -> OrchestratorResult:
        """quiz (marks) -> evaluator (records) -> gamification (awards)"""
        from app.core.schemas import QuizQuestion

        question = QuizQuestion(**{k: v for k, v in quiz.items()
                                    if k in QuizQuestion.__dataclass_fields__})
        marked = self.quiz.mark(question, answer_index)

        progress = self.store.get_progress(user_id)
        progress.quiz_scores.append({"concept": question.concept_key,
                                      "correct": marked["correct"], "score": 1.0 if marked["correct"] else 0.0})
        if marked["correct"]:
            if question.concept_key in progress.weak_topics:
                progress.weak_topics.remove(question.concept_key)
            if question.concept_key not in progress.strong_topics:
                progress.strong_topics.append(question.concept_key)
        elif question.concept_key and question.concept_key not in progress.weak_topics:
            progress.weak_topics.append(question.concept_key)
        self.store.put_progress(user_id, progress)

        award = self.gamification.award(user_id, "quiz_correct" if marked["correct"] else "quiz_incorrect",
                                         question.concept_key)
        message = marked["feedback"] + f"\n\n+{award['xp_awarded']} XP ({award['total_xp']} total)."
        if award["new_badges"]:
            message += f" Badge earned: {', '.join(award['new_badges'])}."

        return self._assemble(user_id, "quiz", message, [], data={"marked": marked, "award": award})

    def submit_challenge(self, user_id: str, challenge: dict, answer: str) -> OrchestratorResult:
        """evaluator -> gamification"""
        ch = Challenge(**{k: v for k, v in challenge.items() if k in Challenge.__dataclass_fields__})
        response = self.evaluator.run(challenge=ch, answer=answer, user_id=user_id)
        result = response.data["evaluation"]

        award = self.gamification.award(
            user_id, "challenge_completed" if result["correct"] else "challenge_partial", ch.concept_key)

        message = response.message + f"\n\n+{award['xp_awarded']} XP ({award['total_xp']} total)."
        if award["new_badges"]:
            message += f" Badge earned: {', '.join(award['new_badges'])}."
        if result["next_difficulty"] == "easier":
            message += "\n\nI'll bring this concept back before we move on."

        return self._assemble(user_id, "practice", message, [response])

    def chat(self, user_id: str, text: str, df: pd.DataFrame | None = None) -> OrchestratorResult:
        """
        The single conversational entry point. Classifies the intent, then runs
        that intent's workflow. This is the method the /chat endpoint and the
        demo both go through.
        """
        self.store.touch_streak(user_id)
        intent, reason, used_llm = self.classify(text)
        session = self._load_session(user_id)
        responses: list[AgentResponse] = []

        if intent == "onboard":
            result = self.onboard(user_id, text)
            result.intent = intent
            return result

        if intent == "analyze_data":
            if df is not None:
                return self.upload_dataset(user_id, df)
            if session["analysis"]:
                stored = {k: v for k, v in session["analysis"].items()
                          if k in DatasetAnalysis.__dataclass_fields__}
                return self._assemble(user_id, intent,
                                       self.data_agent.summarize(DatasetAnalysis(**stored)), responses)
            return self._assemble(user_id, intent,
                                   "Upload a CSV and I'll analyse it -- structure, quality issues and "
                                   "what it can support.", responses)

        if intent == "learn":
            return self.next_lesson(user_id, df=df)

        if intent == "visualize":
            response = self.visualization.run(question=text, analysis=session["analysis"], df=df,
                                               profile=session["profile"])
            responses.append(response)
            return self._assemble(user_id, intent, response.message, responses)

        if intent == "quiz":
            path = self._ensure_path(user_id, session["profile"], session["analysis"], responses)
            lesson = self._current_lesson(path, max(1, session["progress"].current_step - 1))
            concept = lesson.concept_key if lesson else "rows_and_columns"
            response = self.quiz.run(concept_key=concept, profile=session["profile"])
            responses.append(response)
            return self._assemble(user_id, intent, response.message, responses)

        if intent == "practice":
            path = self._ensure_path(user_id, session["profile"], session["analysis"], responses)
            lesson = self._current_lesson(path, max(1, session["progress"].current_step - 1))
            concept = lesson.concept_key if lesson else "rows_and_columns"
            response = self.practice.run(concept_key=concept, profile=session["profile"],
                                          analysis=session["analysis"])
            responses.append(response)
            return self._assemble(user_id, intent, response.message, responses)

        if intent == "progress":
            response = self.gamification.run(user_id=user_id)
            responses.append(response)
            return self._assemble(user_id, intent, response.message, responses)

        # "question": a general query. The profiler still runs, because people
        # reveal their role and level while asking about something else.
        profile_response = self.profiler.run(text=text, profile=session["profile"])
        if profile_response.data["newly_learned"]:
            save_profile(user_id, UserProfile.from_dict(profile_response.data["profile"]), self.store)
            responses.append(profile_response)

        message = self._general_answer(text, session)
        return self._assemble(user_id, "question", message, responses)

    def _general_answer(self, text: str, session: dict) -> str:
        """
        A general question, answered from the learner's own context rather than
        deflected. With no LLM this points them at the most relevant next step,
        which is more useful than a generic definition.
        """
        if self.llm_enabled:
            from app.personalization.user_profile import describe_learner
            facts = []
            if session["analysis"]:
                facts.append(f"Their dataset has columns: {', '.join(session['analysis'].get('columns', []))}.")
            answer = self.llm.complete(
                "You answer a data-science question for a non-specialist in 3-4 plain sentences. "
                "Never invent numbers about their data; only use the facts given. No markdown.",
                f"Learner: {describe_learner(session['profile'])}\n"
                f"Facts about their data:\n{chr(10).join(facts) or '- (no dataset uploaded)'}\n\n"
                f"Their question: {text}",
                max_tokens=400)
            if answer:
                return answer

        path = session["path"]
        if path and path.get("lessons"):
            step = session["progress"].current_step
            upcoming = next((l for l in path["lessons"] if l["step"] >= step), path["lessons"][-1])
            return (f"Good question. The clearest way in is your next lesson: \"{upcoming['title']}\" -- "
                    f"{upcoming['objective']} Say \"next lesson\" and I'll walk you through it "
                    f"using your own data.")
        return ("Tell me what you do and what you'd like to get out of this, and I'll build you a "
                "learning path. If you have a CSV, upload it and I'll teach from your own data.")

    # ------------------------------------------------------------------ assembly

    def _assemble(self, user_id: str, intent: str, message: str,
                  responses: list[AgentResponse], questions: list[str] | None = None,
                  data: dict | None = None) -> OrchestratorResult:
        session = self._load_session(user_id)
        result = OrchestratorResult(
            message=message,
            intent=intent,
            agents_called=[r.agent for r in responses],
            responses=[r.to_dict() for r in responses],
            profile=session["profile"].to_dict(),
            progress=self.gamification.summary(user_id),
            followup_questions=questions or [],
        )
        if data:
            result.responses.append({"agent": "orchestrator", "intent": intent, "data": data})
        return result

    def run(self, user_id: str = "demo_user", text: str = "", df: pd.DataFrame | None = None,
            **kwargs) -> AgentResponse:
        result = self.chat(user_id, text, df)
        return self._respond(result.intent, result.message, result.to_dict())

    def agent_registry(self) -> list[dict]:
        """What each specialist is responsible for -- used by /agents and the docs."""
        return [a.describe() for a in (
            self.profiler, self.data_agent, self.curriculum, self.teacher, self.visualization,
            self.quiz, self.practice, self.gamification, self.evaluator)]
