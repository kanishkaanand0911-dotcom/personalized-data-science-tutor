"""
Progress and memory. JSON-file-backed for the MVP, behind a small interface
so swapping in SQLite or a real database later means implementing one class,
not touching any agent.

What is persisted is deliberately the whole learner: profile, position in
the path, what they got right, what they got wrong, and their XP/badges.
Weak topics come straight from quiz/challenge misses, which is what lets
the curriculum and quiz agents adapt on the next turn rather than restarting
the learner from scratch each session.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import date, datetime

from app.core.config import settings

# XP thresholds. Level N needs LEVEL_STEP * N XP; deliberately flat so a
# demo run visibly levels up rather than sitting at level 1 forever.
LEVEL_STEP = 60


@dataclass
class Progress:
    user_id: str = "demo_user"
    xp: int = 0
    level: int = 1
    badges: list[str] = field(default_factory=list)
    current_step: int = 1
    completed_lessons: list[int] = field(default_factory=list)
    quiz_scores: list[dict] = field(default_factory=list)
    challenge_scores: list[dict] = field(default_factory=list)
    weak_topics: list[str] = field(default_factory=list)
    strong_topics: list[str] = field(default_factory=list)
    streak_days: int = 1
    last_active: str = ""
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Progress":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


def to_jsonable(value):
    """
    Make pandas/numpy values safe to persist.

    The dataset analysis carries real pandas output -- Timestamps as dict keys
    (from a resampled time series), numpy scalars from stats, NaN from empty
    columns. json.dump rejects all three, so they are converted here rather
    than each agent having to remember to clean up after pandas.
    """
    import math

    if isinstance(value, dict):
        return {str(to_jsonable(k)): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, (str, bool)) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        # NaN and infinity are valid Python floats but not valid JSON.
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    # numpy / pandas scalars expose .item(); Timestamps and everything else
    # fall through to their string form.
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return to_jsonable(item())
        except (ValueError, TypeError):
            pass
    return str(value)


def level_for_xp(xp: int) -> int:
    return max(1, xp // LEVEL_STEP + 1)


def xp_to_next_level(xp: int) -> int:
    return LEVEL_STEP * level_for_xp(xp) - xp


class StateStore:
    """
    One JSON file per user under STATE_DIR. Reads and writes are lock-guarded
    so the FastAPI layer can serve concurrent requests without interleaving a
    read-modify-write on the same file.
    """

    def __init__(self, state_dir: str | None = None) -> None:
        self.state_dir = state_dir or settings.state_dir
        os.makedirs(self.state_dir, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, user_id: str) -> str:
        safe = "".join(c for c in user_id if c.isalnum() or c in "-_") or "user"
        return os.path.join(self.state_dir, f"{safe}.json")

    # ---------------------------------------------------------------- raw io

    def load(self, user_id: str) -> dict:
        with self._lock:
            path = self._path(user_id)
            if not os.path.exists(path):
                return {"user_id": user_id, "profile": None, "progress": Progress(user_id=user_id).to_dict(),
                        "learning_path": None, "dataset_analysis": None}
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
            except (ValueError, OSError):
                # A corrupted state file must not brick the learner's account --
                # start fresh rather than raising into every endpoint.
                return {"user_id": user_id, "profile": None, "progress": Progress(user_id=user_id).to_dict(),
                        "learning_path": None, "dataset_analysis": None}

    def save(self, user_id: str, state: dict) -> None:
        with self._lock:
            path = self._path(user_id)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(to_jsonable(state), fh, indent=2)
            os.replace(tmp, path)   # atomic, so a crash mid-write can't truncate the file

    # ---------------------------------------------------------------- typed helpers

    def get_progress(self, user_id: str) -> Progress:
        return Progress.from_dict(self.load(user_id).get("progress") or {"user_id": user_id})

    def put_progress(self, user_id: str, progress: Progress) -> None:
        state = self.load(user_id)
        state["progress"] = progress.to_dict()
        self.save(user_id, state)

    def update(self, user_id: str, **fields) -> dict:
        state = self.load(user_id)
        state.update(fields)
        self.save(user_id, state)
        return state

    def touch_streak(self, user_id: str) -> Progress:
        """
        Bumps the streak once per calendar day. A gap of more than one day
        resets it to 1 -- the streak has to mean something to be motivating.
        """
        progress = self.get_progress(user_id)
        today = date.today().isoformat()
        if progress.last_active == today:
            return progress
        if progress.last_active:
            try:
                gap = (date.fromisoformat(today) - date.fromisoformat(progress.last_active)).days
            except ValueError:
                gap = 1
            progress.streak_days = progress.streak_days + 1 if gap == 1 else 1
        progress.last_active = today
        self.put_progress(user_id, progress)
        return progress

    def log_event(self, user_id: str, event: str, detail: dict | None = None) -> None:
        progress = self.get_progress(user_id)
        progress.history.append({
            "at": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            "detail": detail or {},
        })
        progress.history = progress.history[-100:]   # bounded, so the file can't grow forever
        self.put_progress(user_id, progress)

    def reset(self, user_id: str) -> None:
        path = self._path(user_id)
        if os.path.exists(path):
            os.remove(path)


_store: StateStore | None = None


def get_store() -> StateStore:
    global _store
    if _store is None:
        _store = StateStore()
    return _store
