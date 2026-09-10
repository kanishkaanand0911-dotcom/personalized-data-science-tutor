"""
Narration prompt only — tie-break prompt removed, the decision tree is
fully deterministic so there's never an actual tie to break.

Key design point: A's log entries now include `reason`, a deterministic,
already-correct technical explanation. The LLM's job shrank from
"figure out what happened" to "say it more naturally" — so the prompt
explicitly forbids introducing any number that isn't already in `reason`.
An LLM asked to "explain" raw stats will happily invent a plausible-
sounding but wrong figure; an LLM asked to reword an already-correct
sentence has much less room to do that.
"""

NARRATION_SYSTEM_PROMPT = """You explain one step of a data-cleaning-and-modeling agent to a learner watching it work, so they actually learn something, not just get a play-by-play.
Write 2-3 friendly, plain-language sentences: first explain WHY this approach was tried (the underlying idea, in everyday terms), then WHAT happened when it was checked.
No jargon, no markdown, no hedging.
You are given two things that are already correct — a reason the approach was chosen, and a reason for the outcome. Reword both naturally into one flowing explanation, don't contradict either, and never introduce a number that isn't already stated in them.
Output ONLY the final explanation itself. Do not think out loud, do not comment on word choice or formatting, do not explain your reasoning about how to phrase it — just give the finished sentences, nothing else."""

NARRATION_USER_TEMPLATE = """{subject}
Tried: {action}
Why this was tried (already correct — reword, don't invent a different reason): {why_tried}
Result: {status}
Technical reason for the result (already correct — reword, don't recompute): {reason}

Explain this step: first why it was tried, then what happened."""
