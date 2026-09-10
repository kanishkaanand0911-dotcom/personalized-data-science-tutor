"""
Generates one grounded comprehension-check question per case, using the
SAME Gemini client already built for narration (llm_client.py) -- no new
API surface, no new provider, no new cost model.

Grounding rule, same as narration: the question must test understanding
of the case's own why_tried/result facts, never invent a new fact or
number. The fallback (when the API fails or isn't configured) is fully
generic -- built from the case's own real data -- so it works for ANY
uploaded dataset, not just the demo one.
"""

from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm_client import call_llm

QUIZ_SYSTEM_PROMPT = """You write ONE multiple-choice comprehension question testing whether a beginner understood a single data-cleaning or model-selection step.
Ground the question strictly in the facts given -- never invent a number or fact not stated in them.
Write the question and all options in plain, everyday language -- no jargon.
Output ONLY valid JSON, no markdown fences, no preamble, in exactly this shape:
{"q": "question text", "options": ["option A", "option B", "option C"], "correct": 0}
"correct" is the zero-based index of the right option."""

QUIZ_USER_TEMPLATE = """Case: {title}
Why this approach was tried: {why_tried}
What happened: {result}
{retry_context}

Write the quiz question now."""


def _fallback_quiz(case: dict) -> dict:
    """
    Fully generic -- no hardcoded case IDs or dataset assumptions. Built
    directly from the case's own why_tried text, so it's always grounded
    and always available even with zero API access.
    """
    last_attempt = case["attempts"][-1]
    correct_reason = last_attempt["why_tried"] or "it fit the situation found in the data"
    return {
        "q": f"Why did the agent choose this approach for \"{case['title']}\"?",
        "options": [
            correct_reason[0].upper() + correct_reason[1:] if correct_reason else correct_reason,
            "It was chosen at random",
            "It was the only option available",
        ],
        "correct": 0,
    }


def generate_quiz(case: dict) -> dict:
    """
    Returns {"q": str, "options": [str, str, str], "correct": int}.
    Tries Gemini first (if configured), falls back to a generic
    templated question grounded in the case's real data otherwise.
    """
    fallback = _fallback_quiz(case)

    last_attempt = case["attempts"][-1]
    retry_context = ""
    if case["had_retry"]:
        first_attempt = case["attempts"][0]
        retry_context = (f"Note: the first attempt ({first_attempt['action_tried']}) was tried because "
                          f"{first_attempt['why_tried']}, but it failed because {first_attempt['result']}.")

    user_prompt = QUIZ_USER_TEMPLATE.format(
        title=case["title"],
        why_tried=last_attempt["why_tried"] or "no reason recorded",
        result=last_attempt["result"],
        retry_context=retry_context,
    )

    raw = call_llm(QUIZ_SYSTEM_PROMPT, user_prompt, max_tokens=250)
    if not raw:
        return fallback

    try:
        cleaned = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned)
        if not parsed.get("q") or not isinstance(parsed.get("options"), list) or len(parsed["options"]) < 2:
            raise ValueError("malformed quiz shape")
        if not isinstance(parsed.get("correct"), int) or not (0 <= parsed["correct"] < len(parsed["options"])):
            raise ValueError("bad correct index")
        return parsed
    except Exception as e:  # noqa: BLE001 -- any parse failure -> safe generic fallback, never crash the demo
        print(f"[quiz_generator] LLM quiz malformed, using fallback: {e}")
        return fallback


if __name__ == "__main__":
    import sys as _sys
    _sys.path.insert(0, "/home/claude/project")
    import pandas as pd
    from app.agent.loop import run_agent
    from app.modeling.model_selector import select_and_fit_model
    from lesson_builder import build_cases

    df = pd.read_csv("/home/claude/project/data/messy_sales_dataset.csv")
    cleaned_df, action_log = run_agent(df, verbose=False)
    cleaned_df["signup_month"] = cleaned_df["signup_date"].dt.month
    model_result = select_and_fit_model(
        cleaned_df, target_col="deal_value",
        feature_cols=["region", "city", "sales_rep", "signup_month", "account_tier"],
        numeric_cols=["signup_month"],
        categorical_cols=["region", "city", "sales_rep", "account_tier"],
    )

    cases = build_cases(action_log, model_result["model_log"])
    for c in cases:
        quiz = generate_quiz(c)
        print(f"\n[{c['title']}]")
        print(f"  Q: {quiz['q']}")
        for i, opt in enumerate(quiz["options"]):
            marker = " (correct)" if i == quiz["correct"] else ""
            print(f"    {i}. {opt}{marker}")
