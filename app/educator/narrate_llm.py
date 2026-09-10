"""
narrate_llm.py

The deterministic explainer (explain_action / explain_model) is the real
fallback, not a stub — it's what runs whenever no API key is set or the
call fails, and it's built directly from A's `reason` field, so it's
already correct, just plainer. The LLM's only job is to reword that into
something warmer for a live demo.

generate_lesson(action_log, model_log) is the single function Person C's
Streamlit UI should call: it returns one ready-to-display block of text,
identical in shape whether or not an API key is configured.

Run directly to see both paths:
    python3 narrate_llm.py
"""

from __future__ import annotations

from schemas import ActionLogEntry, ModelLogEntry
from prompts import NARRATION_SYSTEM_PROMPT, NARRATION_USER_TEMPLATE
from llm_client import call_llm


def explain_action(entry: ActionLogEntry) -> str:
    status = "worked" if entry.passed else "didn't work"
    why = f" We tried this because {entry.why_tried}." if entry.why_tried else ""
    return f"On '{entry.column}', tried {entry.action_tried} — it {status}: {entry.reason}.{why}"


def explain_model(entry: ModelLogEntry) -> str:
    status = "was kept" if entry.passed else "was rejected"
    why = f" We tried this model because {entry.why_tried}." if entry.why_tried else ""
    return f"Tried {entry.model_tried}, which {status}: {entry.reason}.{why}"


def narrate_llm(entry: ActionLogEntry | ModelLogEntry) -> str:
    """Explain one log entry — LLM rewording if a key is configured and the
    call succeeds, otherwise the deterministic explanation, unchanged."""
    if isinstance(entry, ActionLogEntry):
        fallback = explain_action(entry)
        subject = f"Column: {entry.column} (issue type: {entry.issue_type})"
        action, status = entry.action_tried, "worked" if entry.passed else "didn't work"
    else:
        fallback = explain_model(entry)
        subject = "Model selection step"
        action, status = entry.model_tried, "kept" if entry.passed else "rejected"

    user_prompt = NARRATION_USER_TEMPLATE.format(
        subject=subject, action=action, status=status, reason=entry.reason,
        why_tried=entry.why_tried or "not specified — just explain the outcome",
    )
    result = call_llm(NARRATION_SYSTEM_PROMPT, user_prompt, max_tokens=80)
    return result if result else fallback


def generate_lesson(action_log: list[ActionLogEntry], model_log: list[ModelLogEntry]) -> str:
    """The single function Person C's UI calls. Same shape regardless of
    whether the LLM is configured — only the sentence wording changes."""
    lines = ["## What happened to your data"]
    lines += [f"- {narrate_llm(entry)}" for entry in action_log]

    if model_log:
        lines.append("")
        lines.append("## Model selection")
        lines += [f"- {narrate_llm(entry)}" for entry in model_log]

    return "\n".join(lines)


if __name__ == "__main__":
    from fake_data import FAKE_ACTION_LOG, FAKE_MODEL_LOG
    import os

    key_status = "SET" if os.environ.get("GEMINI_API_KEY") else "NOT SET — using deterministic fallback"
    print(f"GEMINI_API_KEY: {key_status}\n")
    print(generate_lesson(FAKE_ACTION_LOG, FAKE_MODEL_LOG))
