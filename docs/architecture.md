# Architecture & Agentic Justification

## The agentic loop, explicitly

Two independent instances of the same loop shape run in this system:

**Loop 1 — Cleaning** (per column with a detected issue)
```
observe   → compute_stats() reads the column's current state
decide    → decision tree picks the next untried candidate strategy
act       → the candidate function is applied to a COPY of the data
evaluate  → compute_stats() re-reads the result, compared against
            the pre-action state using a statistical threshold
adapt     → pass: commit the change, move to the next issue
            fail: discard the change, try the next candidate
            (all candidates exhausted: flag for human review)
```

**Loop 2 — Model selection** (once, after cleaning)
```
observe   → correlation strength between features and target
decide    → start with the simplest model justified by that signal
act       → fit the candidate model
evaluate  → cross-validated R², plus a residual-pattern check
            (does the model's error correlate with its own
            predictions? that indicates missed structure, not noise)
adapt     → pass: keep this model
            fail: escalate to a more flexible model family
            (all candidates exhausted: flag for human review)
```

## Why this can't be a deterministic pipeline

A fixed pipeline could apply "median imputation" as a rule and stop. It
has no mechanism to notice that median imputation just quietly distorted
the data, because it never re-examines its own output against the
original. The evaluate → adapt step is the entire difference: this system
checks its own work and changes strategy based on what it finds, which a
fixed sequence of steps cannot do by definition.

**Concrete evidence, not a claim:** on the demo dataset's `deal_value`
column (missing values on a bimodal distribution — small deals mixed with
large enterprise deals), the first candidate strategy (median imputation)
distorts the skew by 21.3%, fails the evaluation threshold, and is
discarded. The system then tries KNN imputation, which distorts skew by
only 7.6%, and is accepted. This sequence is produced by running the
actual code against real data — it is not scripted to demonstrate
adaptation, it happens because the evaluation genuinely rejected the
first attempt.

## Why this can't be "just an LLM"

An LLM asked to "clean this data and explain what you did" can narrate a
plausible-sounding cleaning process without any actual mechanism to
verify its own claims are true, and has no reliable way to compute
exact statistical thresholds or apply the same fix deterministically
twice. This system inverts that: all cleaning, evaluation, and model
selection is deterministic code (pandas, scikit-learn, explicit
thresholds) — auditable and reproducible. The LLM's only role is
narration: turning an already-correct, already-computed `reason` string
into a plain-language sentence for someone without a data science
background. It is explicitly instructed never to introduce a number that
isn't already present in that reason, specifically to prevent the LLM
from inventing plausible-but-wrong statistics.

## Component data flow

| Stage | Input | Output | Deterministic or LLM |
|---|---|---|---|
| `detect_issues` | raw DataFrame | list of `Issue` objects | Deterministic |
| Decision tree | an `Issue` | ordered list of candidate strategies | Deterministic (static mapping) |
| Action functions | DataFrame + column | new DataFrame (copy) | Deterministic |
| `compute_stats` | DataFrame + column | stats dict (nulls, skew, unique count, etc.) | Deterministic |
| Evaluation (`_passes_check`) | before/after stats | pass/fail + reason | Deterministic (threshold-based) |
| `run_downstream_checks` | cleaned DataFrame | pass/fail per real-world task (aggregation, chart, trend) | Deterministic |
| `select_and_fit_model` | cleaned DataFrame + target | chosen model + full attempt log | Deterministic decision logic; standard scikit-learn model fitting |
| `narrate_llm` / `generate_lesson` | a log entry (already-correct `reason`) | plain-language sentence | LLM (Claude), reword-only; deterministic template fallback |

## Failure handling

If every candidate strategy for a column (or every candidate model) fails
its evaluation check, the system does not loop indefinitely or silently
pick the least-bad option. It logs the column/model as unresolved and
flags it for human review, with the specific reason each attempt failed
attached. This is deliberate: the system is designed to fail honestly
rather than fabricate confidence, which was verified directly — removing
the one genuinely predictive feature from the demo dataset causes every
regression model to correctly fail its evaluation and get flagged, rather
than the system pretending one of them worked.

## Anticipated judge questions

**"Why not a normal LLM?"** An LLM has no mechanism to guarantee its
cleaning claims are statistically true, or to apply the identical
transformation deterministically across a full column. This system uses
an LLM only for the part language models are actually good at —
natural-language explanation of an already-correct decision — not for
the decision itself.

**"Why not a deterministic workflow?"** A fixed workflow has no way to
detect that one of its own steps produced a worse result, because it
never re-examines its output. This system's defining behavior — discard
a fix that failed its own check, try a better one — is impossible in a
pipeline with no evaluation step.

**"What decisions are autonomous?"** Which cleaning strategy to try next
per column; whether to accept or discard each attempt; whether to
escalate to a more flexible model; whether to flag a column/model for
human review instead of forcing a low-confidence result.

**"How does it evaluate itself?"** Statistical comparison of before/after
state against explicit thresholds (e.g., skew shift, cross-validated R²,
residual-prediction correlation) — not a vibe-based LLM judgment.

**"What happens if a step fails?"** The next candidate strategy is tried
automatically; if all candidates for a given column or model are
exhausted, the system stops guessing and flags it for a human, with the
specific reasons every attempt failed.
