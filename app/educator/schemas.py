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


@dataclass
class ModelLogEntry:
    model_tried: str
    eval: dict[str, Any]  # cv_r2_mean, test_r2, residual_pattern_corr, ...
    passed: bool
    reason: str
