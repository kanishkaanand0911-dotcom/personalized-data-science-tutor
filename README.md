# AutoTriage-Clean: An Agentic Data Cleaning & Modeling Educator

An AI agent that cleans a user's own messy dataset, verifies its work actually
holds up, picks an appropriate ML model for it, and explains every decision
in plain language — built for people with zero data science background.

## The problem

Non-technical professionals (sales, ops, HR) have real data they want to
understand, but existing options are two extremes: generic DS courses using
textbook datasets, or nothing at all. People end up avoiding their own data,
outsourcing it, or fumbling through it without real understanding.

## Why this needs to be an agent, not a script or a chatbot

A fixed cleaning script applies one rule per problem and hopes for the best.
An LLM chatbot can *describe* cleaning steps but has no mechanism to check
whether its own actions actually worked. This system does neither — it:

1. **Observes** the data and detects real problems (missing values,
   inconsistent category labels, inconsistent formats)
2. **Decides** which fix to try first, based on the problem type
3. **Acts** — applies the fix
4. **Evaluates** — re-inspects the data afterward against statistical
   thresholds (does the fix actually hold up, or did it quietly distort
   the data?)
5. **Adapts** — if the fix failed the check, it's discarded and a more
   sophisticated strategy is tried instead

The same loop runs a second time for model selection: the agent tries a
simple model first, checks its cross-validated fit and residual pattern,
and escalates to more flexible models only when there's a concrete,
measured reason to.

**Concrete example, not hypothetical:** on a sales dataset with a bimodal
deal-size column (mostly small deals, some large enterprise deals),
median imputation for missing values distorts the distribution by 21%.
The agent's evaluation step catches this, discards the fix, and switches
to KNN imputation, which distorts it by only 7.6% — a genuine
try → fail → adapt cycle, not a scripted demo.

## Architecture

```
                        ┌─────────────────┐
   User uploads  ─────► │  detect_issues   │  observes the data,
   raw, messy           │                  │  classifies problems
   dataset               └────────┬─────────┘
                                  │
                                  ▼
                        ┌─────────────────┐
                        │  decision tree   │  decides which fix
                        │                  │  to try, in order
                        └────────┬─────────┘
                                  │
                     ┌────────────┴────────────┐
                     ▼                          │
            ┌─────────────────┐                │
            │   action_fn()    │  acts          │
            └────────┬─────────┘                │
                     ▼                          │
            ┌─────────────────┐                │
            │  compute_stats   │  evaluates:    │
            │  before vs after │  did it work?  │
            └────────┬─────────┘                │
                     │                          │
              pass ──┤── fail ───────────────────┘
                     │      (try next candidate,
                     ▼       or flag for human review)
            ┌─────────────────┐
            │ downstream_check │  final verification:
            │                  │  can the data actually
            └────────┬─────────┘  be used? (aggregation,
                     │             chart, trend)
                     ▼
            ┌─────────────────┐
            │  model_selector  │  same observe→decide→act
            │  (2nd agentic    │  →evaluate→adapt loop,
            │   loop)          │  applied to model choice
            └────────┬─────────┘
                     ▼
            ┌─────────────────┐
            │ educator/narrate │  turns every log entry into
            │  (LLM + fallback)│  plain-language explanation
            └────────┬─────────┘
                     ▼
              User sees: cleaned data, working chart/model,
              and a step-by-step explanation of every decision
              the agent made and why.
```

### Component breakdown

| Component | What it does | Deterministic or LLM-driven |
|---|---|---|
| `detect_issues` | Scans columns, classifies problems | Deterministic (rule-based) |
| Decision tree | Orders candidate fixes per problem type | Deterministic |
| Action functions | Apply a specific fix | Deterministic |
| `compute_stats` / evaluation | Checks whether a fix actually worked | Deterministic (statistical thresholds) |
| `downstream_check` | Verifies the cleaned data is genuinely usable | Deterministic |
| `model_selector` | Picks and validates a regression model | Deterministic decision logic, standard sklearn models |
| `educator/narrate` | Explains every decision in plain language | LLM (Claude), with a deterministic fallback if the API is unavailable |

**Why rule-based planning, not LLM-driven planning:** auditable, fast,
free per-decision, and defensible to judges — "if X then Y" is provable;
"the LLM decided" is not. The LLM's role is deliberately narrow: explaining
decisions that were already made deterministically, never making the
decisions itself. This also means the system degrades gracefully — if the
LLM API is unavailable, the agent still works, just with plainer
explanations.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env  # add your ANTHROPIC_API_KEY for LLM narration (optional)
```

## Running it

```bash
python3 run_full_demo.py
```

Runs the full pipeline against the included demo dataset
(`messy_sales_dataset.csv`) and prints every stage: raw data, cleaning
with backtracking, downstream verification, model selection, and the
plain-language explanation a real user would see.

Without `ANTHROPIC_API_KEY` set, narration falls back to deterministic
template text automatically — the pipeline never breaks due to a missing
key or a failed API call.

## Example: the adaptation moment

```
[issue] deal_value: missing_numeric (severity=medium)
  -> tried impute_median: FAILED (backtracking) -- skew shifted 21.3%
     (2.186 -> 2.651), exceeds 15.0% threshold -- distribution distorted
  -> tried impute_knn: PASSED -- skew shift 7.6%, within 15.0% threshold
```

## Limitations

- Fuzzy category matching currently uses Python's `difflib` (no internet
  access during development to install `rapidfuzz`); swap in `rapidfuzz`
  for better real-world performance — see `requirements.txt`.
- Known-alias mapping for category normalization (e.g. "Bombay" → "Mumbai")
  is a small manual dictionary, not learned — string similarity alone
  cannot catch aliases that don't look similar as strings.
- Model selection currently supports regression only, using scikit-learn's
  built-in models (Linear, Ridge, Random Forest, Gradient Boosting).
- The downstream check runs once, after cleaning finishes; it does not
  currently trigger a second cleaning pass if it fails.

## Team

- **Person A** — agentic core: detection, cleaning actions, evaluation
  logic, backtracking loop, downstream verification, model selection loop
- **Person B** — LLM narration layer: prompt design, API integration,
  deterministic fallback
- **Person C** — Streamlit demo UI, dataset preparation, documentation,
  demo script
