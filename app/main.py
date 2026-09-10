"""
FastAPI backend.

Thin on purpose: every endpoint validates its input, calls the orchestrator,
and returns what came back. No teaching logic, no scoring and no data analysis
lives here -- that all belongs to the agents, so the demo script and the API
exercise exactly the same code path.

Run it with:
    uvicorn app.main:app --reload

FastAPI is an OPTIONAL dependency. If it isn't installed, importing this module
raises a clear message instead of a bare ImportError, and nothing else in the
platform depends on it -- demo_personalized.py and run_full_demo.py both run
without it.
"""

from __future__ import annotations

import io
import os

try:
    from fastapi import FastAPI, File, HTTPException, UploadFile
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "The API layer needs FastAPI: pip install 'fastapi>=0.110' 'uvicorn>=0.27' 'python-multipart>=0.0.9'. "
        "The rest of the platform (demo_personalized.py, run_full_demo.py, the agents) runs without it."
    ) from e

import pandas as pd

from app.agents.orchestrator import Orchestrator
from app.core.config import settings
from app.core.state import get_store
from app.llm.llm_client import llm_status
from app.personalization.user_profile import get_or_create_profile

app = FastAPI(
    title="Personalized Data Science Tutor",
    description="A multi-agent tutor that teaches data science through the learner's own role, level, goal and dataset.",
    version="1.0.0",
)

orchestrator = Orchestrator()
store = get_store()

# Uploaded frames are cached in memory per user so a chart can be rendered on a
# later request without re-reading the file. The saved CSV on disk is the
# durable copy -- this is only a cache, and it is rebuilt from disk on a miss.
_frames: dict[str, pd.DataFrame] = {}


# ---------------------------------------------------------------- request models

class OnboardRequest(BaseModel):
    user_id: str = "demo_user"
    message: str = Field(..., description="What the learner says about themselves")


class ChatRequest(BaseModel):
    user_id: str = "demo_user"
    message: str


class QuizAnswerRequest(BaseModel):
    user_id: str = "demo_user"
    quiz: dict
    answer_index: int


class ChallengeSubmitRequest(BaseModel):
    user_id: str = "demo_user"
    challenge: dict
    answer: str


class AnalyzeRequest(BaseModel):
    user_id: str = "demo_user"
    target_col: str | None = None


# ---------------------------------------------------------------- helpers

def _frame_for(user_id: str) -> pd.DataFrame | None:
    """The learner's dataset: from the in-memory cache, else re-read from the
    CSV saved at upload time."""
    if user_id in _frames:
        return _frames[user_id]
    path = os.path.join(settings.upload_dir, f"{user_id}.csv")
    if os.path.exists(path):
        frame = pd.read_csv(path)
        _frames[user_id] = frame
        return frame
    return None


def _cleaned_frame_for(user_id: str) -> pd.DataFrame | None:
    """The cleaned frame charts should be drawn from -- an uncleaned date column
    is still text, and a line chart of text is meaningless."""
    raw = _frame_for(user_id)
    if raw is None:
        return None
    from app.agent.loop import run_agent
    cleaned, _ = run_agent(raw, verbose=False)
    return cleaned


# ---------------------------------------------------------------- endpoints

@app.get("/")
def root() -> dict:
    return {
        "service": "Personalized Data Science Tutor",
        "llm": llm_status(),
        "agents": orchestrator.agent_registry(),
        "endpoints": ["/onboard", "/upload-data", "/chat", "/learning-path", "/lesson/current",
                      "/quiz/answer", "/challenge/submit", "/progress", "/profile", "/analyze-data",
                      "/agents", "/chart"],
    }


@app.get("/agents")
def agents() -> dict:
    return {"agents": orchestrator.agent_registry()}


@app.post("/onboard")
def onboard(request: OnboardRequest) -> dict:
    return orchestrator.onboard(request.user_id, request.message).to_dict()


@app.post("/upload-data")
async def upload_data(user_id: str = "demo_user", target_col: str | None = None,
                      file: UploadFile = File(...)) -> dict:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a .csv file.")

    contents = await file.read()
    try:
        frame = pd.read_csv(io.BytesIO(contents))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not read that CSV: {e}") from e

    if frame.empty:
        raise HTTPException(status_code=400, detail="That CSV has no rows in it.")

    settings.ensure_dirs()
    frame.to_csv(os.path.join(settings.upload_dir, f"{user_id}.csv"), index=False)
    _frames[user_id] = frame

    return orchestrator.upload_dataset(user_id, frame, target_col=target_col).to_dict()


@app.post("/analyze-data")
def analyze_data(request: AnalyzeRequest) -> dict:
    frame = _frame_for(request.user_id)
    if frame is None:
        raise HTTPException(status_code=404, detail="No dataset uploaded for this user yet.")
    return orchestrator.upload_dataset(request.user_id, frame, target_col=request.target_col).to_dict()


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    return orchestrator.chat(request.user_id, request.message,
                             df=_cleaned_frame_for(request.user_id)).to_dict()


@app.get("/learning-path")
def learning_path(user_id: str = "demo_user") -> dict:
    path = store.load(user_id).get("learning_path")
    if not path:
        raise HTTPException(status_code=404,
                            detail="No learning path yet -- call /onboard first so I know who you are.")
    return path


@app.get("/lesson/current")
def current_lesson(user_id: str = "demo_user") -> dict:
    return orchestrator.next_lesson(user_id, df=_cleaned_frame_for(user_id)).to_dict()


@app.post("/quiz/answer")
def quiz_answer(request: QuizAnswerRequest) -> dict:
    return orchestrator.answer_quiz(request.user_id, request.quiz, request.answer_index).to_dict()


@app.post("/challenge/submit")
def challenge_submit(request: ChallengeSubmitRequest) -> dict:
    return orchestrator.submit_challenge(request.user_id, request.challenge, request.answer).to_dict()


@app.get("/progress")
def progress(user_id: str = "demo_user") -> dict:
    return orchestrator.gamification.summary(user_id)


@app.get("/profile")
def profile(user_id: str = "demo_user") -> dict:
    return get_or_create_profile(user_id).to_dict()


@app.get("/chart")
def chart(path: str) -> FileResponse:
    """
    Serve a rendered chart. The path is confined to the configured chart
    directory -- without that check, this endpoint would read any file on the
    host that the process can open.
    """
    chart_dir = os.path.realpath(settings.chart_dir)
    requested = os.path.realpath(path)
    if not requested.startswith(chart_dir + os.sep) or not os.path.exists(requested):
        raise HTTPException(status_code=404, detail="Chart not found.")
    return FileResponse(requested, media_type="image/png")
