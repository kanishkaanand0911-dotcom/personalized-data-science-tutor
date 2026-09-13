"""FastAPI surface for the learning app.

Session state lives in memory, keyed by an id the client keeps. Each session
holds the uploaded dataframe, the levels derived from it, one cached
deterministic pipeline run, and the learner's guesses and score.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# app/educator modules import `schemas`, `narrate_llm` etc. as top-level names,
# the same way run_full_demo.py sets things up.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "app" / "educator"))

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

import pandas as pd
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from web import chat as chatbot
from web import pipeline
from web.code_snippets import get_code_snippet

STATIC_DIR = Path(__file__).resolve().parent / "static"
SAMPLE_CSV = _ROOT / "data" / "messy_sales_dataset.csv"

app = FastAPI(title="VYBE Learn", docs_url="/api/docs")

# Needed once the frontend is deployed on a different origin than this
# backend (e.g. Vercel + Render) - same-origin dev/prod-bundled setups never
# hit this. CORS_ALLOW_ORIGINS is a comma-separated list; defaults to the
# local dev origins so nothing changes for local development.
_cors_origins = os.environ.get(
    "CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ session


@dataclass
class Session:
    id: str
    role: str | None = None
    experience: str | None = None
    goal: str | None = None
    df: pd.DataFrame | None = None
    dataset_name: str = ""
    levels: list[dict] = field(default_factory=list)
    run: pipeline.PipelineRun | None = None
    guesses: dict[int, dict] = field(default_factory=dict)
    read_levels: set[int] = field(default_factory=set)  # which levels already earned the read bonus
    quiz_results: dict[int, dict] = field(default_factory=dict)  # level_id -> {results, points}
    model_quiz_result: dict | None = None  # modeling's own quiz - one per session, not per level

    @property
    def points(self) -> int:
        raw = sum(g["points"] for g in self.guesses.values())
        raw += len(self.read_levels) * pipeline.READ_BONUS_POINTS
        raw += sum(r["points"] for r in self.quiz_results.values())
        if self.model_quiz_result:
            raw += self.model_quiz_result["points"]
        return max(0, raw)  # score reads as 0, not negative, even after a run of wrong guesses


SESSIONS: dict[str, Session] = {}
MAX_SESSIONS = 200  # in-memory only; evict oldest when full


def _new_session(role: str | None, experience: str | None, goal: str | None = None) -> str:
    if len(SESSIONS) >= MAX_SESSIONS:
        del SESSIONS[next(iter(SESSIONS))]
    sid = uuid.uuid4().hex
    SESSIONS[sid] = Session(id=sid, role=role, experience=experience, goal=goal)
    return sid


def get_session(request: Request) -> Session:
    sid = request.headers.get("x-session-id") or request.query_params.get("sid")
    if not sid or sid not in SESSIONS:
        raise HTTPException(status_code=401, detail="No active session. Start again from the top.")
    return SESSIONS[sid]


def require_run(session: Session) -> pipeline.PipelineRun:
    if session.run is None:
        raise HTTPException(status_code=409, detail="Load a dataset first.")
    return session.run


# ------------------------------------------------------------------- models


class StartBody(BaseModel):
    role: str | None = None
    experience: str | None = None
    goal: str | None = None


class GuessBody(BaseModel):
    choice_id: str


class ChatBody(BaseModel):
    message: str
    level_id: int | None = None
    learner_id: str | None = None  # stable per-browser id (see lib/api.ts) for the ADK tutor's memory


class QuizBody(BaseModel):
    answers: dict[str, str]


class MentorLessonContext(BaseModel):
    id: str | None = None
    title: str | None = None
    objective: str | None = None
    difficulty: str | None = None
    step: str | None = None  # "learn" | "predict" | "apply" | "explain"


class MentorDatasetContext(BaseModel):
    name: str | None = None
    columns: list[str] = []
    shape: dict | None = None
    sample_rows: list[dict] = []
    summary: dict | None = None
    current_version: str | None = None  # "raw" | "cleaned" | "model_ready"


class MentorBody(BaseModel):
    user_message: str = ""
    current_lesson: MentorLessonContext | None = None
    dataset: MentorDatasetContext | None = None
    current_code: str | None = None
    last_output: str | None = None
    last_error: str | None = None
    attempt_count: int = 0
    hints_used: int = 0
    learning_mode: str = "assisted"  # "guided" | "assisted" | "independent"
    mastery_level: int = 0
    previous_mistakes: list[str] = []
    recent_actions: list[str] = []
    action: str | None = None  # explain | hint | why_wrong | example | explain_output | next_step
    learner_id: str | None = None


# ------------------------------------------------------------------- routes


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "llm_narration": bool(os.environ.get("GEMINI_API_KEY"))}


@app.post("/api/session")
def start_session(body: StartBody) -> dict:
    return {"session_id": _new_session(body.role, body.experience, body.goal)}


@app.get("/api/session/state")
def session_state(request: Request) -> dict:
    """Lets a reloaded client pick up where it left off without re-uploading."""
    session = get_session(request)
    if session.df is None:
        return {"stage": "dataset", "profile": {"role": session.role, "experience": session.experience}}
    return {
        "stage": "loaded",
        "profile": {"role": session.role, "experience": session.experience},
        "dataset": pipeline.dataset_summary(session.df, session.dataset_name),
        "roadmap": _roadmap(session),
        "levels": [_public_level(lvl) for lvl in session.levels],
        "guesses": session.guesses,
        "points": session.points,
    }


@app.post("/api/dataset")
async def load_dataset(
    request: Request,
    file: UploadFile | None = None,
    use_sample: str | None = Form(default=None),
) -> dict:
    session = get_session(request)

    if use_sample or file is None:
        raw = SAMPLE_CSV.read_bytes()
        name = "Sample sales dataset"
    else:
        raw = await file.read()
        name = file.filename or "your dataset"

    try:
        df = pipeline.load_csv(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=422, detail="That file could not be read as a CSV.")

    try:
        levels = pipeline.build_levels(df, session.role)
        run = pipeline.run_pipeline(df)
    except Exception as exc:  # noqa: BLE001 - surface a clean message, not a 500 page
        raise HTTPException(
            status_code=422,
            detail=f"The agent could not process this dataset ({exc}).",
        )

    session.df = df
    session.dataset_name = name
    session.levels = levels
    session.guesses = {}
    session.read_levels = set()
    session.quiz_results = {}
    session.model_quiz_result = None
    session.run = run

    return {
        "dataset": pipeline.dataset_summary(df, name),
        "roadmap": _roadmap(session),
        "levels": [_public_level(lvl) for lvl in session.levels],
    }


@app.get("/api/roadmap")
def roadmap(request: Request) -> dict:
    return _roadmap(get_session(request))


@app.get("/api/levels")
def levels(request: Request) -> dict:
    session = get_session(request)
    return {"levels": [_public_level(lvl) for lvl in session.levels], "points": session.points}


@app.post("/api/levels/{level_id}/read")
def mark_read(level_id: int, request: Request) -> dict:
    """Awards a small, one-time bonus for reaching a level's explanation -
    understanding something is worth a little, independent of whether the
    guess that follows is right."""
    session = get_session(request)
    if level_id < 0 or level_id >= len(session.levels):
        raise HTTPException(status_code=404, detail="No such level.")
    awarded = level_id not in session.read_levels
    session.read_levels.add(level_id)
    return {"awarded": awarded, "points_total": session.points}


def _guess_result(session: Session, run: pipeline.PipelineRun, level_id: int, submitted_choice_id: str | None = None) -> dict:
    """The full learner-facing shape of a scored guess - reveal is computed
    from the cached deterministic run and never depends on the guess itself.
    Shared by submit_guess (the live path) and resume_session (rebuilding it
    for an already-scored level, where only the minimal {choice_id, correct,
    points} was ever persisted)."""
    level = session.levels[level_id]
    reveal = pipeline.level_reveal(run, level)
    prior = session.guesses[level_id]
    return {
        "correct": prior["correct"],
        "points_awarded": prior["points"],
        "points_total": session.points,
        "your_choice": prior["choice_id"],
        "locked": submitted_choice_id is not None and prior["choice_id"] != submitted_choice_id,
        "agent_choice": reveal["agent_choice"],
        "agent_choice_label": reveal["agent_choice_label"],
        "resolved": reveal["resolved"],
        "attempts": reveal["attempts"],
        "next_level": level_id + 1 if level_id + 1 < len(session.levels) else None,
    }


@app.post("/api/levels/{level_id}/guess")
def submit_guess(level_id: int, body: GuessBody, request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    if level_id < 0 or level_id >= len(session.levels):
        raise HTTPException(status_code=404, detail="No such level.")

    if level_id not in session.guesses:
        level = session.levels[level_id]
        reveal = pipeline.level_reveal(run, level)
        score = pipeline.score_guess(level, reveal, body.choice_id)
        session.guesses[level_id] = {
            "choice_id": body.choice_id,
            "correct": score["correct"],
            "points": score["points"],
        }

    return _guess_result(session, run, level_id, body.choice_id)


@app.get("/api/levels/{level_id}/code")
def level_code(level_id: int, request: Request) -> dict:
    """The real code behind the fix the agent actually kept for this
    column, plus one plain-language sentence explaining it - see
    web/code_snippets.py. Only ever the strategy that was really used,
    never a generic tutorial snippet."""
    session = get_session(request)
    run = require_run(session)
    if level_id < 0 or level_id >= len(session.levels):
        raise HTTPException(status_code=404, detail="No such level.")
    level = session.levels[level_id]
    reveal = pipeline.level_reveal(run, level)
    if not reveal["resolved"]:
        return {"available": False, "label": None, "code": None, "explain": None}
    snippet = get_code_snippet(reveal["agent_choice"])
    if snippet is None:
        return {"available": False, "label": reveal["agent_choice_label"], "code": None, "explain": None}
    return {"available": True, "label": reveal["agent_choice_label"], **snippet}


@app.get("/api/levels/{level_id}/quiz")
def level_quiz(level_id: int, request: Request) -> dict:
    """A quick, low-stakes recap quiz for a level the learner has already
    guessed on. Never sends the correct answer to the client - it can always
    be regenerated deterministically at grading time instead."""
    session = get_session(request)
    run = require_run(session)
    if level_id < 0 or level_id >= len(session.levels):
        raise HTTPException(status_code=404, detail="No such level.")
    level = session.levels[level_id]
    reveal = pipeline.level_reveal(run, level)
    questions = pipeline.build_quiz(level, reveal)
    return {"questions": [{"id": q["id"], "prompt": q["prompt"], "options": q["options"]} for q in questions]}


@app.post("/api/levels/{level_id}/quiz")
def submit_quiz(level_id: int, body: QuizBody, request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    if level_id < 0 or level_id >= len(session.levels):
        raise HTTPException(status_code=404, detail="No such level.")

    level = session.levels[level_id]
    reveal = pipeline.level_reveal(run, level)
    questions = pipeline.build_quiz(level, reveal)

    # Same locked-in-on-first-submission rule as a guess: resubmitting
    # doesn't let you retry your way to more points.
    prior = session.quiz_results.get(level_id)
    if prior is None:
        prior = pipeline.score_quiz(questions, body.answers)
        session.quiz_results[level_id] = prior

    return {
        "results": prior["results"],
        "correct_answers": {q["id"]: q["answer"] for q in questions},
        "points_awarded": prior["points"],
        "points_total": session.points,
    }


def _model_data(run: pipeline.PipelineRun) -> dict:
    return {k: v for k, v in run.model.items() if k != "raw_model_log"}


@app.get("/api/model/code")
def model_code(request: Request) -> dict:
    """The real code behind the model the agent actually chose, plus one
    plain-language sentence explaining it - see web/code_snippets.py."""
    session = get_session(request)
    run = require_run(session)
    model = _model_data(run)
    chosen = model.get("chosen")
    if not chosen:
        return {"available": False, "label": None, "code": None, "explain": None}
    snippet = get_code_snippet(chosen["model"])
    if snippet is None:
        return {"available": False, "label": chosen["label"], "code": None, "explain": None}
    return {"available": True, "label": chosen["label"], **snippet}


@app.get("/api/model/quiz")
def model_quiz(request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    questions = pipeline.build_model_quiz(_model_data(run))
    return {"questions": [{"id": q["id"], "prompt": q["prompt"], "options": q["options"]} for q in questions]}


@app.post("/api/model/quiz")
def submit_model_quiz(body: QuizBody, request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    questions = pipeline.build_model_quiz(_model_data(run))

    if session.model_quiz_result is None:
        session.model_quiz_result = pipeline.score_quiz(questions, body.answers)

    return {
        "results": session.model_quiz_result["results"],
        "correct_answers": {q["id"]: q["answer"] for q in questions},
        "points_awarded": session.model_quiz_result["points"],
        "points_total": session.points,
    }


@app.post("/api/chat")
def chat(body: ChatBody, request: Request) -> dict:
    session = get_session(request)
    level = None
    if body.level_id is not None and 0 <= body.level_id < len(session.levels):
        level = session.levels[body.level_id]
    context = chatbot.build_context(session.role, session.experience, session.goal, level)
    # The ADK tutor's memory should survive across visits, so it's keyed by
    # the browser's own persistent id when the client sends one, not this
    # backend session's in-memory (and much shorter-lived) id.
    learner_id = _safe_learner_id(body.learner_id) or session.id
    result = chatbot.ask(body.message, context, session_id=learner_id, level=level)

    # The ADK tutor's own profiler/gamification agents are a richer source of
    # truth than our onboarding quiz - fold what they learned back into this
    # session so it actually reshapes the UI (level analogies, Mission 1
    # copy, callouts), not just this one chat bubble. Never overwrite what
    # the learner already told us directly.
    profile = result.get("profile")
    if profile:
        session.role = session.role or profile.get("role") or profile.get("domain")
        session.experience = session.experience or profile.get("experience_level")
        session.goal = session.goal or profile.get("learning_goal")

    return {
        "reply": result["reply"],
        "grounded": result["grounded"],
        "progress": result.get("progress"),
    }


@app.post("/api/mentor")
def mentor(body: MentorBody, request: Request) -> dict:
    """The platform-wide AI Mentor - unlike /api/chat (scoped to one cleaning
    level), this takes a full context object from wherever the learner
    currently is (lesson, dataset, code, output, error, mode, hint/attempt
    counts) and routes it through the same ADK -> Gemini -> fallback chain."""
    session = get_session(request)
    learner_id = _safe_learner_id(body.learner_id) or session.id
    payload = body.model_dump()
    result = chatbot.mentor_ask(payload, session_id=learner_id)
    return {"reply": result["reply"], "grounded": result["grounded"], "mode": body.learning_mode}


@app.get("/api/levels/{level_id}/callouts")
def level_callouts(level_id: int, request: Request) -> dict:
    session = get_session(request)
    if level_id < 0 or level_id >= len(session.levels):
        raise HTTPException(status_code=404, detail="No such level.")
    level = session.levels[level_id]
    lines, grounded = chatbot.callouts(level, session.role, session.experience, session.goal)
    return {"callouts": lines, "grounded": grounded}


@app.get("/api/verify")
def verify(request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    return run.downstream


@app.get("/api/visualize")
def visualize(request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    return pipeline.visualization_data(run.cleaned_df)


@app.get("/api/model")
def model(request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    return {k: v for k, v in run.model.items() if k != "raw_model_log"}


@app.get("/api/results")
def results(request: Request) -> dict:
    session = get_session(request)
    run = require_run(session)
    cleaned = run.cleaned_df
    head = cleaned.head(6).round(2)
    for col in head.select_dtypes(include=["datetime64[ns]"]).columns:
        head[col] = head[col].dt.strftime("%Y-%m-%d")
    preview = head.astype(object).where(pd.notna(head), None)
    return {
        "points_total": session.points,
        "levels_total": len(session.levels),
        "levels_correct": sum(1 for g in session.guesses.values() if g["correct"]),
        "columns_changed": run.columns_changed,
        "cleaned_preview": preview.to_dict(orient="records"),
        "cleaned_columns": list(cleaned.columns),
        "downstream_passed": run.downstream["overall_passed"],
        "model": {k: v for k, v in run.model.items() if k != "raw_model_log"},
        "lesson": run.lesson,
    }


# ------------------------------------------------------------------ helpers


def _roadmap(session: Session) -> dict:
    n_issues = len(session.levels)
    return {
        "dataset_name": session.dataset_name,
        # The learning path this app teaches, stage by stage - node keys are
        # what the frontend routes on, titles are the curriculum's own names.
        "nodes": [
            {
                "key": "cleaning",
                "title": "Data Cleaning",
                "detail": f"{n_issues} issue{'s' if n_issues != 1 else ''} to work through"
                if n_issues
                else "nothing to fix here",
            },
            {"key": "verify", "title": "Verification", "detail": "check the data actually works"},
            {
                "key": "visualize",
                "title": "Exploratory Data Analysis",
                "detail": "summarize the data, chart it, and find relationships",
            },
            {
                "key": "ml_foundations",
                "title": "Machine Learning Foundations",
                "detail": "features, target, and what kind of problem this is",
            },
            {
                "key": "model",
                "title": "Model Selection & Evaluation",
                "detail": "compare algorithms and choose one that fits",
            },
            {"key": "results", "title": "Final Project", "detail": "your complete, portfolio-ready analysis"},
        ],
    }


def _safe_learner_id(raw: str | None) -> str | None:
    """The learner id becomes a URL path segment when talking to the ADK
    connector (see chat.py::_adk_session_url) - keep it to characters that
    are safe there, same allowlist the connector's own set_learner_id uses."""
    if not raw:
        return None
    safe = "".join(c for c in raw if c.isalnum() or c in "-_")
    return safe or None


def _public_level(level: dict) -> dict:
    return {
        "id": level["id"],
        "column": level["column"],
        "issue_type": level["issue_type"],
        "severity": level["severity"],
        "title": level["title"],
        "analogy": level["analogy"],
        "question": level["question"],
        "options": level["options"],
        "guess_kind": level["guess_kind"],
    }


# ------------------------------------------------------------------ static


app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(STATIC_DIR / "styles.css")


@app.get("/app.js")
def appjs() -> FileResponse:
    return FileResponse(STATIC_DIR / "app.js")


@app.exception_handler(HTTPException)
def http_exc(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})
