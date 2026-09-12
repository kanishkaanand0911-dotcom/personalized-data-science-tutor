"""
ADK tool wrappers around the existing multi-agent tutor.

None of these functions contain any new logic. Each one is a thin adapter
that calls straight into the already-tested `app/` package (the same code
`demo_personalized.py` and `app/main.py` use) and returns a plain dict, which
is what an ADK FunctionTool needs.

Keeping the logic in `app/` and not here means:
  - the deterministic facts (pandas/scikit-learn results, rule-based
    curriculum, XP/badge rules) are computed exactly as before -- ADK never
    invents a number about the learner's data.
  - the existing pytest suite under tests/ keeps covering this behaviour
    unchanged.

Long-term memory: the learner's profile, progress, learning path and dataset
analysis all live in `app/core/state.py::StateStore`, one JSON file per
learner under `data/state/<learner_id>.json`. That file is what makes the
platform "remember" a learner across visits, not anything ADK-specific.

The learner id defaults to ADK's own `tool_context.user_id` -- the id the
client passed when it opened the session (see client_ui/, which keeps a
stable id in the browser's localStorage). So the same browser reconnecting
days later, even in a brand new ADK session, resumes the same profile, XP,
level, weak topics and dataset analysis automatically, with no extra step.
`set_learner_id` exists only for the rarer case where a learner explicitly
asks to be tracked under a different name than the client's own id.
"""

from __future__ import annotations

import os
import sys

# Make the project root (parent of this package) importable as `app.*`
# regardless of the working directory `adk web` was launched from.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pandas as pd
from google.adk.tools.tool_context import ToolContext

from app.agents.orchestrator import Orchestrator
from app.core.config import settings
from app.personalization.user_profile import get_or_create_profile

_orchestrator = Orchestrator()

DEFAULT_USER_ID = "demo_user"


def _uid(tool_context: ToolContext) -> str:
    """The StateStore key this session's learner is tracked under.

    Priority: an explicit override set via `set_learner_id` this session,
    then the id the client connected with (`tool_context.user_id` -- stable
    across visits for a given browser/client), then a hardcoded fallback so
    ad-hoc testing (e.g. curl, the ADK dev UI's default user) still works.
    """
    return (tool_context.state.get("learner_id")
            or tool_context.user_id
            or DEFAULT_USER_ID)


def set_learner_id(learner_id: str, tool_context: ToolContext) -> dict:
    """Track this conversation under a different learner id than the client's own.

    Only call this if the learner explicitly asks to be tracked under a
    specific name/id different from how the client identified them.
    Normally you do NOT need to call this -- the client's own persistent id
    already ties the conversation to the right learner's saved profile and
    progress across visits.

    Args:
        learner_id: A short identifier for the learner, e.g. their name.

    Returns:
        The learner id now in effect for this session.
    """
    safe = "".join(c for c in learner_id if c.isalnum() or c in "-_") or DEFAULT_USER_ID
    tool_context.state["learner_id"] = safe
    return {"learner_id": safe}


def chat_with_tutor(message: str, tool_context: ToolContext) -> dict:
    """Send the learner's message through the full tutor pipeline.

    This routes the message through the same orchestrator used by the
    platform's API and demo script: intent classification, then whichever
    specialist agents that intent needs (profiler, data analyst, curriculum,
    teacher, visualization, quiz, practice, evaluator, gamification).

    Use this for ordinary conversation -- onboarding ("I'm in sales, I'm a
    beginner..."), asking to learn ("teach me the next lesson"), asking for
    a chart, a quiz, a practice challenge, or a progress check. Relay the
    returned `message` back to the learner; if `followup_questions` is
    non-empty, ask the learner those questions too.

    Args:
        message: The learner's own words, verbatim.

    Returns:
        A dict with `message`, `intent`, `agents_called`, `profile`,
        `progress`, and `followup_questions`.
    """
    user_id = _uid(tool_context)
    result = _orchestrator.chat(user_id, message)
    return result.to_dict()


def upload_dataset(csv_path: str, tool_context: ToolContext, target_col: str | None = None) -> dict:
    """Load and analyze a CSV dataset for the current learner.

    Reads the CSV from a local file path, runs the same deterministic
    analysis the platform always runs (structure, data-quality issues, the
    observe/decide/act/evaluate/adapt cleaning loop, EDA, and -- if
    `target_col` is given -- model selection), stores it against the
    learner's profile, and rebuilds their learning path around what the
    dataset can actually support.

    Args:
        csv_path: Absolute or relative path to a .csv file on disk.
        target_col: Optional column name to train a regression model
            against. Leave unset if the learner just wants the data
            analysed, not modeled.

    Returns:
        A dict with the orchestrator's summary message, the learner's
        rebuilt learning path, and the full dataset analysis.
    """
    user_id = _uid(tool_context)
    if not csv_path or not os.path.exists(csv_path):
        return {"error": f"No file found at '{csv_path}'. Give a path to a .csv file on this machine."}

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:  # noqa: BLE001
        return {"error": f"Could not read that CSV: {e}"}

    if df.empty:
        return {"error": "That CSV has no rows in it."}

    settings.ensure_dirs()
    df.to_csv(os.path.join(settings.upload_dir, f"{user_id}.csv"), index=False)

    result = _orchestrator.upload_dataset(user_id, df, target_col=target_col)
    return result.to_dict()


def get_progress(tool_context: ToolContext) -> dict:
    """Get the current learner's XP, level, badges, streak, and weak/strong topics."""
    return _orchestrator.gamification.summary(_uid(tool_context))


def get_profile(tool_context: ToolContext) -> dict:
    """Get the current learner's structured profile (role, experience level, goal, etc.)."""
    return get_or_create_profile(_uid(tool_context)).to_dict()


def list_agents() -> dict:
    """List every specialist agent in the tutor platform and what it's responsible for."""
    return {"agents": _orchestrator.agent_registry()}
