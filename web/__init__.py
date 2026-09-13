"""Web layer for AutoTriage-Clean: a thin FastAPI wrapper around the existing
agentic backend in app/, plus the gamified learning frontend it serves.

Nothing in here makes cleaning or modeling decisions. Every decision still comes
from app/agent, app/evaluation, and app/modeling. This layer only sequences the
backend calls, shapes their output for the screens, and scores the learner's
guesses without ever letting a guess change the agent's real output.
"""
