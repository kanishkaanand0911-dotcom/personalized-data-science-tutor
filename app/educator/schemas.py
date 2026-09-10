"""
Schemas matching Person A's real log shapes exactly — no guessing anymore.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ActionLogEntry:
    column: str
    issue_type: str
    action_tried: str
    before_stats: dict[str, Any]
    after_stats: dict[str, Any]
    passed: bool
    reason: str          # A already computes this — the LLM rephrases it, never invents it
    why_tried: str = ""  # the reasoning BEHIND trying this strategy (not just the outcome) —
                          # default empty string keeps old callers (e.g. fake_data.py) working unchanged
    tradeoff: str = ""   # NEW: this strategy's honest weakness, for pros/cons display


@dataclass
class ModelLogEntry:
    model_tried: str
    eval: dict[str, Any]  # cv_r2_mean, test_r2, residual_pattern_corr, ...
    passed: bool
    reason: str
    why_tried: str = ""  # same idea, for model choice
    tradeoff: str = ""   # NEW: this model's honest weakness, for pros/cons display
