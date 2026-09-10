# AutoTriage-Clean — Status & Handoff Doc

*Last updated: Day 1-2 of hackathon. Written for the team, especially Person C.*

---

## 1. What this project actually is

An AI agent that:
1. Takes a user's own messy dataset
2. Cleans it — genuinely checking its own work and switching strategy when a fix fails
3. Verifies the cleaned data can actually be used (not just "looks clean")
4. Picks an appropriate ML model for it, with the same check-and-adapt behavior
5. Explains every decision in plain language, for someone with zero data science background

It is NOT a fixed script and NOT a chatbot pretending to clean data — every claim above has been tested against real output, not just designed on paper (see Section 4).

---

## 2. What's built — Person A (agentic core)

### 2.1 Detection (`app/agent/detect.py`)
- Scans every column, classifies exactly 3 problem types: missing values, inconsistent category labels (e.g. "Mumbai"/"mumbai"/"Bombay"), and format errors (dates/numbers stored as inconsistent strings)
- Uses fuzzy string matching (`difflib`, standing in for `rapidfuzz` — see Section 6) plus a manual alias table for name variants that don't look similar as strings (e.g. "Bombay" → "Mumbai")
- Fixed a bug where clean structured ID columns (e.g. "Rep_1", "Rep_12") were false-flagged as inconsistent labels

### 2.2 Evaluation (`app/evaluation/stats.py`)
- `compute_stats()` — the function every decision depends on: null %, dtype, skew, unique count, sample values
- Fixed a pandas 3.0 bug where string columns weren't being detected as categorical (pandas changed how it types CSV-loaded string columns)

### 2.3 Action functions (`app/actions/actions.py`)
- One function per fix strategy: `impute_median`, `impute_knn`, `impute_mode`, `normalize_categories`, `coerce_numeric_strings`, `coerce_dates`
- Fixed a bug where `impute_knn` was silently converting an ID column to floats

### 2.4 The cleaning loop (`app/agent/loop.py`)
- Ties detection → decision tree → action → evaluation → backtrack together
- **Verified live**: on the demo dataset's `deal_value` column, median imputation is tried first, distorts the distribution by 21.3%, gets rejected, and the system falls back to KNN imputation (7.6% distortion, accepted) — a real adaptation, not scripted
- If every candidate strategy fails, the column is flagged for human review instead of the system faking confidence (tested directly with a genuinely unsolvable column)

### 2.5 Downstream verification (`app/evaluation/downstream.py`)
- After cleaning, runs 3 real tasks against the cleaned data: aggregation (groupby + mean), a time-series trend, and an actual rendered chart
- This proves the data is genuinely usable, not just "statistically cleaner" — a column can pass per-column checks and still break a real downstream task, so this is a separate, final check

### 2.6 Model selection (`app/modeling/model_selector.py`)
- A second, independent agentic loop, same shape as cleaning: observe data → decide starting model → fit → evaluate (cross-validated R² + residual pattern check) → escalate if it fails
- Escalation ladder: Linear Regression → Ridge → Random Forest → Gradient Boosting (only escalates when there's a measured reason to, not brute-force "try everything")
- **Verified both outcomes**: with a genuinely predictive feature (`account_tier`) in the data, Linear Regression passes immediately (R²=0.288); with that feature removed, every model honestly fails and gets flagged for human review rather than pretending to work

### 2.7 Tests (`tests/test_core.py`)
- 5 tests covering: stat correctness, no false positives on clean ID columns, and — most importantly — an independently-seeded backtrack test (different random data than the demo CSV) confirming the adaptation behavior isn't a fluke tuned to one dataset

---

## 3. What's built — Person B (narration/educator layer)

### 3.1 Design
- `app/educator/schemas.py` — exact data shapes matching A's real log output (`ActionLogEntry`, `ModelLogEntry`)
- `app/educator/prompts.py` — the system prompt instructing the LLM to reword A's already-correct `reason` field, never invent new numbers or facts
- `app/educator/llm_client.py` — low-level API wrapper: retry with backoff, in-memory caching, and critically, **graceful fallback**: if the API fails or isn't configured, falls back to deterministic template text instead of crashing
- `app/educator/narrate_llm.py` — `generate_lesson(action_log, model_log)`, the single function the UI should call
- `app/educator/test_harness.py` — 4 offline tests (mocked API), no real key needed to verify the logic

### 3.2 Provider: Gemini, not Anthropic
- Switched from Anthropic to **Google Gemini** specifically because Gemini's free tier is permanent (no card, no expiry) vs. Anthropic's one-time trial credit
- Old Anthropic version preserved at `app/educator_anthropic_backup/` in case needed later
- Model: `gemini-3.6-flash` (note: `gemini-2.5-flash`, originally used, was deprecated for new users mid-build — confirmed via a live API error, not guesswork)

### 3.3 Bugs found and fixed during real-device testing
- **Human-review fallback entries broke B's schema** — A's loop emitted `action_tried: None` with missing `before_stats`/`after_stats` when every strategy failed; fixed to emit `"flag_for_human_review"` with real stats attached, matching B's tested convention
- **`.env` file wasn't actually being read** — a `.env` file existing on disk doesn't automatically load into Python; added `python-dotenv` + `load_dotenv()` call, which was missing entirely
- **Model name deprecated mid-project** — `gemini-2.5-flash` → `gemini-3.6-flash`, caught via a live 404 error on the real machine
- **Severe output truncation** — narration was coming back as sentence fragments (e.g. "I tried filling in", ", no hedging."). Root cause: newer Gemini models consume part of the token budget on internal processing before the visible answer, so an 80-token ceiling produced almost nothing. Fixed in two steps: raised the ceiling to 900 tokens, and tightened the system prompt to stop the model from narrating its own reasoning about word choice/formatting instead of just answering
- **Confirmed working end-to-end on real hardware** (Windows, real Gemini API key) after these fixes — all 6 log entries now produce complete, coherent, genuinely plain-language explanations

---

## 4. Proof this actually works (not just claimed)

Ran directly on a real Windows machine, real API key, real dataset:

> "We tried filling in the missing deal values with the middle value, but it distorted the overall shape of the data too much... The balance shifted by 21.3%."
>
> "I filled in the missing deal values by using information from similar rows. This only changed the overall shape of the data by 7.7%, which is well within our allowed 15.0% limit."
>
> "We decided to keep the linear regression model because it fits the data well enough to move forward. It achieved an overall fit score of 0.288."

This is the real backtrack (median failing → KNN succeeding) explained in genuine plain language — the actual product working, not a mockup.

---

## 5. What's expected of Person C

### 5.1 The two functions to build against — both real, both stable
```python
from app.agent.loop import run_agent
cleaned_df, action_log = run_agent(raw_df)   # the cleaning + backtrack loop

from app.modeling.model_selector import select_and_fit_model
model_result = select_and_fit_model(cleaned_df, target_col=..., feature_cols=..., numeric_cols=..., categorical_cols=...)

from app.educator.schemas import ActionLogEntry, ModelLogEntry
from app.educator.narrate_llm import generate_lesson
lesson_text = generate_lesson(
    [ActionLogEntry(**e) for e in action_log],
    [ModelLogEntry(**e) for e in model_result["model_log"]],
)
```
`lesson_text` is ready-to-display markdown-ish text — no further processing needed.

### 5.2 Streamlit UI — not started, this is the main open task
Needs, at minimum:
- File upload widget (accepts CSV)
- A "Run" button that calls `run_agent()` then `select_and_fit_model()` then `generate_lesson()`
- A live or post-hoc log panel showing each cleaning/model step (this is where the "agent thinking out loud" visual effect should live — judges respond well to seeing this)
- A final results view: the cleaned data table, the chart from the downstream check, and the plain-language lesson text

### 5.3 Demo dataset — already built, don't rebuild
`data/messy_sales_dataset.csv` is included in the project. It has all 3 issue types planted deliberately, plus an engineered bimodal `deal_value` column specifically designed to trigger the median→KNN backtrack on camera. Use this as-is for the demo.

### 5.4 What NOT to build
- No tie-breaker LLM call — the decision tree is fully deterministic, there's never an actual tie
- No second cleaning pass triggered by downstream-check failure — out of scope for the timeline, downstream check is a final report-only verification

### 5.5 Setup, same as A/B went through
```
pip install -r requirements.txt
copy .env.example .env
```
Get a free Gemini key at aistudio.google.com/apikey (no card required), paste into `.env`, then:
```
python run_full_demo.py
```
to see the whole pipeline run end-to-end before building the UI around it.

---

## 6. Known limitations (be ready to answer these if judges ask)

- Fuzzy category matching uses Python's built-in `difflib`, not `rapidfuzz` (no internet access during initial development to install it) — swap in for better real-world performance if time allows
- Model selection supports regression only (Linear/Ridge/Random Forest/Gradient Boosting), not classification
- Downstream check runs once after cleaning finishes; it does not trigger a second cleaning pass if it fails — a design choice made deliberately to fit the timeline
- The narration style has two slightly different formats depending on which version of the explainer runs (grouped retry narrative vs. flat per-attempt bullets) — worth a quick team decision on which to standardize on for the final demo

---

## 7. File structure reference

```
project/
├── README.md                          -- project overview, architecture diagram
├── requirements.txt
├── .env.example                       -- copy to .env, add GEMINI_API_KEY
├── run_full_demo.py                   -- run this to see everything end-to-end
├── data/
│   └── messy_sales_dataset.csv        -- the demo dataset, use as-is
├── docs/
│   ├── architecture.md                -- judge-facing "why is this agentic" defense
│   └── status-and-handoff.md          -- this file
├── app/
│   ├── agent/          -- detect.py, loop.py, issue.py (cleaning core)
│   ├── actions/         -- actions.py (fix strategies)
│   ├── evaluation/       -- stats.py, downstream.py
│   ├── modeling/         -- model_selector.py
│   ├── educator/          -- Gemini narration (current, working)
│   └── educator_anthropic_backup/  -- old Anthropic version, kept for reference
└── tests/
    └── test_core.py       -- run with: python tests/test_core.py
```
