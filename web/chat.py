"""The study screen's chatbot. Free-text questions try the ADK-hosted
multi-agent tutor first (tutor_agent/, a separate project - real profiling,
curriculum and gamification behind the reply), then fall back to the
existing direct Gemini wrapper in app/educator/llm_client.py (already on
sys.path via web/api.py), then to a deterministic message. Each tier returns
None/falsy on any failure, so a stage never being available just means the
next one runs - the chat never breaks just because a key or a second server
isn't there.
"""

from __future__ import annotations

import os

import requests

SYSTEM_PROMPT = """You are the friendly mascot tutor inside a learning app called VYBE Learn.
The learner is a non-technical professional or student, not a data scientist.
Answer their question in 2-4 short, plain sentences. Define any technical term you use in the
same sentence, don't just drop it. Never invent a number or fact about their dataset that
wasn't given to you in the context below - if you don't have it, say so plainly.
If they ask how to fix something, give them a pointer or a nudge toward the idea, not the
complete final answer outright - this is a lesson, not an answer key.
No markdown, no bullet lists, no em dashes, no headers."""


def build_context(role: str | None, experience: str | None, goal: str | None, level: dict | None) -> str:
    lines: list[str] = []
    if role:
        lines.append(f"Learner's role: {role}")
    if experience:
        lines.append(f"Their data experience: {experience}")
    if goal:
        lines.append(f"What they're hoping to get out of this: {goal}")
    if level:
        lines.append(f"Current topic: {level['title']}, on the column '{level['column']}'")
        lines.append(f"Already explained to them: {level['analogy']}")
    return "\n".join(lines)


CALLOUT_SYSTEM_PROMPT = """You write 3 very short callouts for a learner looking at one column of
their own data in a data-cleaning lesson. Each callout is at most 12 words, plain language, no
jargon. Callout 1: one real fact about why this issue matters, using only the fact given below -
never invent a number. Callout 2: a pointer toward how to think about fixing it - a nudge, not
the final answer. Callout 3: a short encouraging line. Output exactly 3 lines, one callout per
line, nothing else - no numbering, no markdown, no quotes."""


def callouts(level: dict, role: str | None, experience: str | None, goal: str | None) -> tuple[list[str], bool]:
    """Short 'what can I do here' callouts for the top of the study screen -
    LLM-written when connected, grounded in the same real facts every time."""
    option_labels = ", ".join(o["label"] for o in level.get("options", []))
    context = build_context(role, experience, goal, level)
    prompt = f"{context}\nCandidate fixes for this column: {option_labels}"

    try:
        from llm_client import call_llm  # app/educator/llm_client.py
    except ImportError:
        call_llm = None

    if call_llm is not None:
        reply = call_llm(CALLOUT_SYSTEM_PROMPT, prompt, max_tokens=150)
        if reply:
            lines = [ln.strip(" -*•") for ln in reply.splitlines() if ln.strip()]
            if lines:
                return lines[:3], True

    return _fallback_callouts(level, option_labels), False


def _fallback_callouts(level: dict, option_labels: str) -> list[str]:
    return [
        f"This column: {level['column']} - {level['title'].lower()}.",
        f"Common fixes here: {option_labels or 'it depends on the column'}.",
        "Think about what a single wrong fix could distort before you commit to it.",
    ]


# ---------------------------------------------------------------- ADK bridge

# The ADK tutor connector: a separate `adk api_server` process hosting
# tutor_agent/ (see D:\...\personalized-data-science-tutor-adk_ui). Optional -
# if it isn't running, ask() below just skips straight to the direct-Gemini
# path, same as before this existed.
ADK_BASE_URL = os.environ.get("ADK_BASE_URL", "http://127.0.0.1:8765")
ADK_APP_NAME = "tutor_agent"
_ADK_TIMEOUT = 15  # a live multi-agent turn does 2+ model calls; give it real time


def _adk_session_url(learner_id: str) -> str:
    return f"{ADK_BASE_URL}/apps/{ADK_APP_NAME}/users/{learner_id}/sessions/{learner_id}"


def _ensure_adk_session(learner_id: str) -> bool:
    """One ADK session per web session id - reused across turns so the
    learner's profile/progress persists within a visit, same as the
    connector's own client_ui does with its browser-local id."""
    url = _adk_session_url(learner_id)
    try:
        res = requests.get(url, timeout=_ADK_TIMEOUT)
        if res.status_code == 404:
            res = requests.post(url, json={}, timeout=_ADK_TIMEOUT)
        return res.ok
    except requests.RequestException:
        return False


def _adk_extract_text(events: list[dict]) -> str | None:
    """The final assistant reply is the last event carrying visible text;
    earlier events in the same turn are tool calls/results with no text."""
    for event in reversed(events):
        parts = (event.get("content") or {}).get("parts") or []
        text = "\n".join(
            p["text"] for p in parts if isinstance(p.get("text"), str) and p["text"].strip()
        )
        if text:
            return text
    return None


def _adk_extract_tool_result(events: list[dict], tool_name: str) -> dict | None:
    """The structured data (profile, progress) a tool call returned - this is
    what makes personalization something the UI can actually use, instead of
    only being visible as words inside the chat reply."""
    for event in reversed(events):
        parts = (event.get("content") or {}).get("parts") or []
        for part in parts:
            fr = part.get("functionResponse")
            if fr and fr.get("name") == tool_name and isinstance(fr.get("response"), dict):
                return fr["response"]
    return None


def ask_adk(message: str, learner_id: str) -> dict | None:
    """Routes a message through the ADK-hosted multi-agent tutor. Returns
    None on any failure (server not running, timeout, empty reply) so the
    caller can fall back to the direct-Gemini path honestly. On success,
    returns {"reply", "profile", "progress"} - profile/progress are the real
    structured facts the tutor's profiler/gamification agents computed, not
    just their wording, so the caller can drive the UI with them directly."""
    if not _ensure_adk_session(learner_id):
        return None
    try:
        res = requests.post(
            f"{ADK_BASE_URL}/run",
            json={
                "appName": ADK_APP_NAME,
                "userId": learner_id,
                "sessionId": learner_id,
                "newMessage": {"role": "user", "parts": [{"text": message}]},
            },
            timeout=_ADK_TIMEOUT,
        )
        if not res.ok:
            return None
        events = res.json()
        reply = _adk_extract_text(events)
        if not reply:
            return None
        tool_result = _adk_extract_tool_result(events, "chat_with_tutor") or {}
        return {
            "reply": reply,
            "profile": tool_result.get("profile"),
            "progress": tool_result.get("progress"),
        }
    except requests.RequestException:
        return None


def ask(message: str, context: str, session_id: str | None = None, level: dict | None = None) -> dict:
    """Returns {"reply", "grounded", "profile", "progress"} - grounded is
    False only once every live source has been tried and none answered, so
    the UI can say so honestly. profile/progress are only ever populated by
    the ADK tier - the direct-Gemini and deterministic fallbacks have no
    concept of either. `level` is only used to ground the offline FAQ
    fallback in the real column/issue being studied - it never reaches a
    live model differently than it already does via `context`."""
    prompt = f"{context}\n\nLearner's message: {message}" if context else message

    if session_id:
        adk = ask_adk(prompt, session_id)
        if adk:
            return {
                "reply": adk["reply"],
                "grounded": True,
                "profile": adk.get("profile"),
                "progress": adk.get("progress"),
            }

    try:
        from llm_client import call_llm  # app/educator/llm_client.py
    except ImportError:
        call_llm = None  # google-genai itself isn't installed

    if call_llm is not None:
        reply = call_llm(SYSTEM_PROMPT, prompt, max_tokens=300)
        if reply:
            return {"reply": reply, "grounded": True, "profile": None, "progress": None}

    return {"reply": _fallback(message, level), "grounded": False, "profile": None, "progress": None}


# ---------------------------------------------------------------- offline FAQ
#
# When no live model answers, a flat "I can't help with that" is a dead end
# for the single most common thing a curious learner actually does: ask a
# real question. These are real, useful answers to the questions that come
# up constantly in data cleaning/modeling, matched by keyword rather than
# needing a model at all - honest (grounded stays False; this is canned, not
# live-generated) but actually useful instead of a refusal.
FAQ_ANSWERS: list[tuple[list[str], str]] = [
    (
        ["delete the row", "drop the row", "remove the row", "just delete", "just drop"],
        "You could drop rows with blanks instead of filling them in, but that throws away every "
        "other real value in that row too - and if the blanks aren't random (say, only small "
        "deals go unrecorded), dropping them quietly biases whatever you do next. Filling them "
        "in keeps the row usable while being honest about the guess.",
    ),
    (
        ["just use the average", "just use average", "why not average", "why not the mean", "use the mean"],
        "A plain average sounds safe, but one huge outlier can drag it far from where most of "
        "your data actually sits - so every blank gets filled with a number that doesn't "
        "represent most rows. That's exactly why the agent checks whether a fix distorts the "
        "column before keeping it, instead of always trusting the average.",
    ),
    (
        ["what is skew", "what does skew mean", "what's skew"],
        "Skew measures how lopsided a column's numbers are - a skew of 0 means they're spread "
        "evenly around the middle; a high skew means a few very large (or very small) values are "
        "pulling the shape off to one side. The agent checks whether a fix changes that shape too "
        "much, not just whether the blanks got filled in.",
    ),
    (
        ["what is r2", "what is r-squared", "what's r2", "what does r2 mean", "r squared"],
        "R-squared is a score from 0 to 1 for how much of the pattern in your target column a "
        "model actually explains - 1 means it predicts almost perfectly, 0 means it's no better "
        "than guessing the average every time. The agent requires a minimum R-squared before it "
        "will trust a model enough to keep it.",
    ),
    (
        ["how does the agent decide", "how does it decide", "how does the agent choose", "how do you decide"],
        "For each issue, the agent tries the simplest fix first, actually measures what that fix "
        "did to the real data (does it stay close to the original shape, does it still have "
        "blanks, does it parse correctly), and only keeps it if that check passes - otherwise it "
        "moves to the next candidate. Nothing is chosen just because it's the default option.",
    ),
    (
        ["what is imputation", "what does impute mean", "what is imputing"],
        "Imputation just means filling in a blank cell with a reasonable guess instead of leaving "
        "it empty or throwing the row away. The real question is what that guess is based on - a "
        "single flat number for everyone, or something smarter that looks at similar rows.",
    ),
    (
        ["what if i get it wrong", "what happens if i'm wrong", "what happens if i pick wrong"],
        "Nothing about your data changes either way - your guess is only ever scored against what "
        "the agent actually did, never fed back into it. Getting it wrong just costs a few points "
        "and shows you the real reasoning afterward.",
    ),
    (
        ["why does this matter", "why should i care", "why is this important"],
        "Because whatever's wrong in this column stays wrong in every chart, total, or report "
        "built on top of it later - fixing it here, once, with a real check that it worked, is "
        "cheaper than debugging a wrong number three steps downstream.",
    ),
]


def _faq_fallback(message: str, level: dict | None) -> str | None:
    text = message.lower()
    for keywords, answer in FAQ_ANSWERS:
        if any(k in text for k in keywords):
            if level:
                return f"On {level['column']}: {answer}"
            return answer
    return None


def _fallback(message: str, level: dict | None = None) -> str:
    faq = _faq_fallback(message, level)
    if faq:
        return faq
    return (
        "I don't have a live, personalized answer for that specific question right now. Try "
        "asking it a different way, naming one of the approaches listed above for this column, "
        "or ask whoever's running the demo to finish connecting the tutor."
    )


# ------------------------------------------------------------------- mentor
#
# The AI Mentor: a mode-aware guide (guided/assisted/independent) that sits
# across the whole platform rather than one lesson screen. Reuses the exact
# same three-tier fallback (ADK -> direct Gemini -> canned) as ask() above -
# it's the same tutoring brain, just given a richer context object and a
# stricter "don't just hand over the answer" system prompt.

MENTOR_BASE_PROMPT = """You are the AI Mentor inside a Data Science learning platform. You guide
learners through datasets, Python, data cleaning, and machine learning - you coach, you do not just
hand over finished answers. Ground every claim only in the context given below; never invent a
dataset fact, column name, error message, or number that wasn't provided - if something's missing,
say so plainly instead of guessing. Keep replies short: 2-5 plain sentences, no markdown, no bullet
lists, no headers, no em dashes."""

MENTOR_MODE_PROMPTS = {
    "guided": (
        "This learner is struggling. Explain in very simple language, break the task into one small "
        "step at a time, offer a concrete example, and ask at most one question per reply. Give a "
        "small, progressive hint rather than the final answer unless the reveal rule below allows more."
    ),
    "assisted": (
        "This learner is making steady progress. Encourage them to write or try it themselves, name "
        "the relevant concept without solving it for them, give a partial hint, and ask them to try "
        "again before you'd consider revealing a full solution."
    ),
    "independent": (
        "This learner is confident. Give minimal hints, focus on reasoning and interpretation, and ask "
        "them to justify their own code or choice rather than explaining it to them."
    ),
}

MENTOR_REVEAL_RULE = (
    "Only give a complete, final solution if: the learner explicitly asks for it after having already "
    "attempted the task, they've already used the hints available to them, they are clearly repeatedly "
    "stuck on the same thing, or the current task is itself an explanation/review task rather than a "
    "coding task. Otherwise, nudge - don't solve."
)

MENTOR_ACTION_PROMPTS = {
    "explain": "Suggested action clicked: \"Explain this\" - explain the current lesson or task in your usual style for this learning mode.",
    "hint": "Suggested action clicked: \"Give me a hint\" - give exactly one progressive hint, not the answer; make it a little more specific than a hint you'd give on a first attempt if hints_used is already high.",
    "why_wrong": "Suggested action clicked: \"Why is this wrong?\" - explain why the learner's last attempt, code, or output was wrong, grounded only in the context given below.",
    "example": "Suggested action clicked: \"Show an example\" - give one small, concrete example related to the current concept, not the exact solution to their specific task if it's a coding task.",
    "explain_output": "Suggested action clicked: \"Explain the output\" - interpret last_output or last_error below in plain language.",
    "next_step": "Suggested action clicked: \"What should I try next?\" - suggest exactly one concrete next step, not the whole remaining plan.",
}


def _mentor_context_block(payload: dict) -> str:
    lines: list[str] = []
    lesson = payload.get("current_lesson") or {}
    if lesson.get("title"):
        lines.append(
            f"Current lesson: {lesson['title']} (step: {lesson.get('step') or 'n/a'}, "
            f"difficulty: {lesson.get('difficulty') or 'n/a'})"
        )
    if lesson.get("objective"):
        lines.append(f"Lesson objective: {lesson['objective']}")

    dataset = payload.get("dataset") or {}
    if dataset.get("name"):
        cols = ", ".join(dataset.get("columns") or [])
        lines.append(f"Dataset: {dataset['name']}" + (f" - columns: {cols}" if cols else ""))
        shape = dataset.get("shape") or {}
        if shape:
            lines.append(f"Shape: {shape.get('rows', '?')} rows x {shape.get('cols', '?')} columns")
        if dataset.get("current_version"):
            lines.append(f"Dataset version right now: {dataset['current_version']}")

    if payload.get("current_code"):
        lines.append(f"Learner's current code:\n{payload['current_code']}")
    if payload.get("last_output"):
        lines.append(f"Last output shown to the learner:\n{payload['last_output']}")
    if payload.get("last_error"):
        lines.append(f"Last error the learner hit:\n{payload['last_error']}")

    if payload.get("attempt_count") is not None:
        lines.append(f"Attempts so far on this task: {payload['attempt_count']}")
    if payload.get("hints_used") is not None:
        lines.append(f"Hints already given for this task: {payload['hints_used']}")
    if payload.get("mastery_level") is not None:
        lines.append(f"Learner's mastery level (0-100): {payload['mastery_level']}")

    mistakes = payload.get("previous_mistakes") or []
    if mistakes:
        lines.append("Recent mistakes: " + "; ".join(mistakes[-3:]))
    actions = payload.get("recent_actions") or []
    if actions:
        lines.append("Recent actions taken: " + "; ".join(actions[-5:]))

    return "\n".join(lines)


def mentor_ask(payload: dict, session_id: str | None = None) -> dict:
    """The AI Mentor's answer. Same honesty contract as ask(): `grounded`
    is only True when a live model (ADK or direct Gemini) actually answered;
    otherwise a genuinely useful canned fallback is returned instead, never
    a fabricated one dressed up as live."""
    mode = payload.get("learning_mode") or "assisted"
    mode_prompt = MENTOR_MODE_PROMPTS.get(mode, MENTOR_MODE_PROMPTS["assisted"])
    system_prompt = f"{MENTOR_BASE_PROMPT}\n\n{mode_prompt}\n\n{MENTOR_REVEAL_RULE}"

    action = payload.get("action")
    action_prompt = MENTOR_ACTION_PROMPTS.get(action) if action else None
    context_block = _mentor_context_block(payload)
    message = (payload.get("user_message") or "").strip()

    prompt_parts = [p for p in [context_block, action_prompt] if p]
    if message:
        prompt_parts.append(f"Learner's message: {message}")
    elif action_prompt:
        prompt_parts.append("(No free-text message - just respond to the suggested action above.)")
    prompt = "\n\n".join(prompt_parts)

    if session_id:
        adk = ask_adk(prompt, session_id)
        if adk:
            return {"reply": adk["reply"], "grounded": True}

    try:
        from llm_client import call_llm  # app/educator/llm_client.py
    except ImportError:
        call_llm = None

    if call_llm is not None:
        reply = call_llm(system_prompt, prompt, max_tokens=350)
        if reply:
            return {"reply": reply, "grounded": True}

    return {"reply": _mentor_fallback(message, action, payload), "grounded": False}


def _mentor_fallback(message: str, action: str | None, payload: dict) -> str:
    if message:
        faq = _faq_fallback(message, None)
        if faq:
            return faq
    if payload.get("last_error") and action in (None, "why_wrong", "explain_output"):
        return (
            "I can't reach a live mentor right now, but here's a general nudge: read the last line of "
            "the error first - it usually names the exact object and operation that failed - then check "
            "that the column or variable you're using actually exists and has the type you expect."
        )
    if action == "hint":
        return (
            "I don't have a live hint generator connected right now - try re-reading the task's own "
            "explanation panel; the next step is usually one idea away from what it already told you."
        )
    if action == "next_step":
        return "I can't reach a live mentor right now - try the next unfinished step in your current lesson's checklist."
    return (
        "I don't have a live, personalized answer for that right now. Try rephrasing your question, or "
        "use one of the suggested actions once the mentor is reconnected."
    )
