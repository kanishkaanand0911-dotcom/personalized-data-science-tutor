# app/educator — LLM narration (updated for real integration)

## What changed from the original plan

- **Schema is now real, not guessed** — `ActionLogEntry` and `ModelLogEntry`
  match A's actual field names (`action_tried`, `issue_type`, `reason`,
  and the new `ModelLogEntry` for model selection, which wasn't in the
  original Day 1 doc).
- **The tie-breaker is gone.** `tie_break.py` and its prompt are deleted.
  A's decision tree is fully deterministic — there's no case where an LLM
  needs to pick between equally-valid strategies. If that changes later
  (some genuinely ambiguous case shows up), it's a small, separate addition
  — don't rebuild it speculatively.
- **The deterministic explainer is the real fallback, not a stub.**
  `explain_action()` / `explain_model()` build their sentence directly from
  A's `reason` field, which is already correct. The LLM's job shrank
  accordingly: it rewords `reason` into something warmer, it does not
  interpret raw stats anymore. The prompt explicitly forbids introducing
  any number not already in `reason` — a model asked to "explain" stats
  will happily invent a plausible-sounding wrong one; a model asked to
  reword an already-correct sentence has far less room to do that.
- **One handoff function for Person C:** `generate_lesson(action_log,
  model_log)` returns a single ready-to-display text block, identical in
  structure whether or not `ANTHROPIC_API_KEY` is set. C's Streamlit panel
  should just render this string. For the before/after chart, C should
  read `before_stats` / `after_stats` directly off each `ActionLogEntry` —
  those aren't touched by narration at all.

## Confirmed working (all offline, no key needed)

```
python3 test_harness.py
```
Covers: no-key silent fallback, total-API-failure fallback, LLM response
used when available, and `generate_lesson()` producing the same structure
either way.

## What you still need to do

1. **Set a real key and read the output for wording quality** — offline
   tests only prove it doesn't crash:
   ```
   export ANTHROPIC_API_KEY=your_key_here
   python3 narrate_llm.py
   ```
2. **Agree the prompt tone with A now**, before building further on top of
   it — current wording is "1-2 friendly, plain-language sentences, no
   jargon." Changing tone (more playful, more formal) is a two-line edit
   in `prompts.py`, cheap now, more annoying once C's demo script is
   written around a specific voice.
3. **Swap in real logs the moment A has them** — replace the import in
   `narrate_llm.py`'s `__main__` block and in `test_harness.py` from
   `fake_data` to A's real log module. If anything breaks, it's almost
   certainly a field-name mismatch in `ActionLogEntry`/`ModelLogEntry`.
