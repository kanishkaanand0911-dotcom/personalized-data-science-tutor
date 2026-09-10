"""
Structured data shapes for the personalized learning platform.

Every agent takes a typed input and returns a typed output -- that's what
makes this a multi-agent system rather than one chatbot with a long prompt.
These are plain dataclasses rather than Pydantic models so the core package
has zero hard dependencies; FastAPI (app/main.py) converts them at the edge.

The existing educator schemas (ActionLogEntry, ModelLogEntry) are deliberately
NOT redefined here -- they already match the cleaning agent's real log shape
and are imported from app.educator.schemas wherever needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# ---------------------------------------------------------------- enums-as-constants

EXPERIENCE_LEVELS = ("beginner", "intermediate", "advanced")

ROLES = (
    "sales", "marketing", "hr", "operations", "finance",
    "data_cleaner", "analyst", "student", "general",
)

LEARNING_GOALS = (
    "understand_dataset",
    "data_cleaning",
    "visualization",
    "eda",
    "feature_engineering",
    "machine_learning",
    "prediction",
    "business_decisions",
)


# ---------------------------------------------------------------- user profile

@dataclass
class UserProfile:
    """
    What the profiler agent produces and every other agent reads.

    Only `role`, `experience_level` and `learning_goal` are load-bearing for
    curriculum generation -- everything else refines the wording or the
    examples used. `confidence` records how much of this was actually stated
    by the user versus inferred, so the orchestrator knows whether it still
    needs to ask an onboarding question.
    """
    user_id: str = "demo_user"
    name: str | None = None
    age: int | None = None
    profession: str | None = None
    role: str = "general"
    domain: str | None = None
    experience_level: str = "beginner"
    current_skills: list[str] = field(default_factory=list)
    learning_goal: str = "understand_dataset"
    secondary_goals: list[str] = field(default_factory=list)
    preferred_learning_style: str = "hands_on"
    dataset_available: bool = False
    dataset_type: str | None = None
    target_task: str | None = None
    confidence: dict[str, float] = field(default_factory=dict)
    raw_statements: list[str] = field(default_factory=list)

    def missing_critical_fields(self) -> list[str]:
        """Fields the system could not infer confidently enough to skip asking about."""
        missing = []
        for f in ("role", "experience_level", "learning_goal"):
            if self.confidence.get(f, 0.0) < 0.5:
                missing.append(f)
        if not self.dataset_available and self.confidence.get("dataset_available", 0.0) < 0.5:
            missing.append("dataset_available")
        return missing

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserProfile":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


# ---------------------------------------------------------------- curriculum

@dataclass
class Lesson:
    """One step of a learning path. `concept_key` links it to teaching content
    and to the data facts a lesson should be grounded in."""
    step: int
    title: str
    concept_key: str
    objective: str
    difficulty: str = "beginner"
    needs_dataset: bool = False
    practice_prompt: str | None = None
    chart_type: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LearningPath:
    role: str
    experience_level: str
    learning_goal: str
    rationale: str
    lessons: list[Lesson] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "experience_level": self.experience_level,
            "learning_goal": self.learning_goal,
            "rationale": self.rationale,
            "lessons": [l.to_dict() for l in self.lessons],
        }


# ---------------------------------------------------------------- dataset analysis

@dataclass
class DatasetAnalysis:
    """
    Everything the data agent learned about the user's file. Every number in
    here comes from pandas/sklearn -- the LLM never computes any of it, it
    only rewords it.
    """
    n_rows: int = 0
    n_cols: int = 0
    columns: list[str] = field(default_factory=list)
    dtypes: dict[str, str] = field(default_factory=dict)
    column_stats: dict[str, dict] = field(default_factory=dict)   # after cleaning
    raw_column_stats: dict[str, dict] = field(default_factory=dict)  # before cleaning
    issues: list[dict] = field(default_factory=list)
    eda: dict = field(default_factory=dict)
    cleaning_log: list[dict] = field(default_factory=list)
    downstream: dict = field(default_factory=dict)
    modeling: dict = field(default_factory=dict)
    suggested_domain: str | None = None
    chart_opportunities: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- teaching / assessment

@dataclass
class TeachingBlock:
    """What the teacher agent returns for one lesson: never a monologue --
    an explanation, a grounded example, and a question back to the learner."""
    lesson_step: int
    title: str
    explanation: str
    example: str
    check_question: str
    grounded_facts: list[str] = field(default_factory=list)
    source: str = "deterministic"   # "llm" | "deterministic"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class QuizQuestion:
    question: str
    options: list[str]
    correct_index: int
    explanation: str = ""
    concept_key: str = ""
    source: str = "deterministic"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Challenge:
    prompt: str
    concept_key: str
    hints: list[str] = field(default_factory=list)
    expected_keywords: list[str] = field(default_factory=list)
    difficulty: str = "beginner"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvaluationResult:
    correct: bool
    score: float
    feedback: str
    matched: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    next_difficulty: str = "same"   # "easier" | "same" | "harder"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- orchestration

@dataclass
class AgentResponse:
    """
    Uniform envelope every agent returns, so the orchestrator can log and
    route without knowing each agent's internals.
    """
    agent: str
    intent: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    used_llm: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OrchestratorResult:
    message: str
    intent: str
    agents_called: list[str] = field(default_factory=list)
    responses: list[dict] = field(default_factory=list)
    profile: dict = field(default_factory=dict)
    progress: dict = field(default_factory=dict)
    followup_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
