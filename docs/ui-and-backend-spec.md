# Backend Capabilities + UI Feature Spec

*For Person C — everything here maps to real, tested code. Nothing in this doc is aspirational.*

---

## 1. The user flow this backend supports

```
1. User opens the app
2. User picks a dataset: bundled example OR upload their own CSV
3. User picks what they want out of it: which column to predict/understand
4. Backend cleans the data (agentic loop, self-correcting)
5. Backend picks and fits a model for the chosen target column
6. Backend turns the whole run into a sequence of "cases" — each with:
   why it was tried, what happened, pros/cons of the options considered,
   the actual code that did it, and a comprehension quiz
7. XP, badges, and a skill-map summary at the end
```

Every step below maps to a real function you can call today.

---

## 2. Backend functions available right now

### Step 2 — Dataset input
**Not yet built**: a bundled-dataset registry (currently only one CSV exists: `data/messy_sales_dataset.csv`). If you want a picker between multiple example datasets, that's a small addition — a folder of CSVs plus a list of `{name, description, path}`. Flag this back to A if you want more than one example dataset; trivial to add, just hasn't been asked for yet.

**Upload flow**: any CSV `pd.read_csv()` can handle works as input — no special backend prep needed before step 4.

### Step 3 — What does the user want?
**Real recommendation, not just "future work":** don't build free-text goal parsing ("what do you want to learn?") for the target column — it's fragile and adds a whole NLP-reliability problem you don't need. Instead:

```python
from app.modeling.column_roles import auto_detect_feature_roles

# after cleaning (step 4), call this with whatever column the user picks:
roles = auto_detect_feature_roles(cleaned_df, target_col=user_chosen_column)
# -> {"feature_cols": [...], "numeric_cols": [...], "categorical_cols": [...]}
```

Show the user a simple dropdown of the dataset's numeric columns ("what do you want to predict?") after cleaning finishes. `auto_detect_feature_roles` then figures out everything else automatically — which columns are usable features, which are IDs to ignore, which are free text to ignore. This works on ANY uploaded dataset, not just the demo one.

### Step 4 — Cleaning (already built, already proven)
```python
from app.agent.loop import run_agent
cleaned_df, action_log = run_agent(raw_df)
```
Self-correcting: tries a strategy, checks if it actually worked, discards and retries with something smarter if not. Verified live on real data (median imputation failing, KNN succeeding).

### Step 5 — Model selection (already built, already proven)
```python
from app.modeling.model_selector import select_and_fit_model
model_result = select_and_fit_model(
    cleaned_df, target_col=user_chosen_column, **roles  # roles from step 3
)
```
Same self-correcting pattern: starts simple, escalates only when there's a measured reason to (weak fit or a non-random error pattern).

**NEW — what's actually driving the prediction:**
```python
from app.modeling.feature_importance import get_feature_importance, explain_feature_importance
importances = get_feature_importance(model_result["chosen_model"], categorical_cols=roles["categorical_cols"])
summary = explain_feature_importance(importances)
# "The single biggest driver was Account tier (Enterprise), responsible for about 17%..."
```
This is genuinely new — it didn't exist before this session. It answers your "what things are affecting the dataset" question directly, with real numbers from the actual fitted model, not a guess.

### Step 6 — Turning the run into teachable cases (already built)
```python
from app.educator.lesson_builder import build_cases
cases = build_cases(action_log, model_result["model_log"], model_result["all_candidates_considered"])
```
One case per column (grouping all its attempts together) plus one case for model selection. Each case now includes:
- `attempts`: what was actually tried, in order, with why + result
- `options_considered`: **NEW** — every strategy the decision tree knows about for this problem type, including ones never needed, each with a `why_tried` (the pro) and a `tradeoff` (the honest con). This is the actual "data scientist weighing pros and cons" content.

**Example of what `options_considered` looks like for a missing-values case, even when only one strategy was needed:**
```
[
  {"name": "impute_median", "why_tried": "...simplest fix...", "tradeoff": "...can distort data with distinct groups...", "was_tried": true},
  {"name": "impute_knn", "why_tried": "...better for grouped data...", "tradeoff": "...needs other related columns, slower...", "was_tried": false}
]
```

### The actual code behind each step (NEW)
```python
from app.educator.code_snippets import get_code_snippet
snippet = get_code_snippet("impute_knn")
# {"code": "imputer = KNNImputer(n_neighbors=5)\n...", "explain": "For each blank cell, this looks at..."}
```
Real code from this project, paired with one plain-language sentence — for an expandable "see the code" section per case.

### Step 6b — Quizzes and narration (already built)
```python
from app.educator.quiz_generator import generate_quiz
from app.educator.narrate_llm import generate_lesson  # flat text version, alternative to per-case rendering

for case in cases:
    quiz = generate_quiz(case)  # {"q": ..., "options": [...], "correct": int}
```
Uses Gemini (free tier), falls back to a generic grounded question if the API is unavailable — never breaks.

### Step 7 — Gamification (already built, stateless)
```python
from app.gamification.rules import badge_for_case, final_badge, XP_RULES
badge = badge_for_case(case)  # e.g. "Detective's Eye" for a case with a genuine retry
```
C's frontend owns the actual XP/streak/badge *state* (persistence) — these functions just answer "does this event earn a badge," given real case data.

---

## 3. UI features needed — screen by screen

### Screen 1 — Dataset picker
- Two options: "Try an example dataset" (shows the bundled CSV(s) with a one-line description) or "Upload your own CSV"
- On upload: basic validation (is it a real CSV, does it have at least 2 columns) before proceeding

### Screen 2 — Pick your goal
- Show the uploaded dataset's column list
- Simple selector: "Which column do you want to understand or predict?" (filtered to numeric columns only, since that's what the model supports)
- **Practice-mode banner, always visible**: "This is a learning exercise — not a real business report"

### Screen 3 — Live agent run
- A progress view that reveals cases one at a time as `run_agent()` and `select_and_fit_model()` produce them (or, simpler for a hackathon timeline: run everything first, then reveal cases one at a time in the UI even though the backend already finished — the "live" feeling matters more than true streaming)
- Each case card shows, in order:
  1. Title + concept tag ("Handling missing data")
  2. What was tried + why (the winning attempt)
  3. If there was a retry: the failed attempt shown first, marked clearly as "didn't work," then the fix that worked
  4. **Expandable "Weigh the options"** section — this is `options_considered`: show every strategy the agent knows for this problem, marked tried/not-tried, each with its pro and con. This is the concrete "data scientist" feeling you asked for.
  5. **Expandable "See the code"** section — the real snippet + one-sentence explanation from `code_snippets.py`
  6. The quiz — one question, immediate feedback, gentle re-explanation on a wrong answer
  7. XP awarded, badge if earned

### Screen 4 — Model case (same card shape, plus)
- **Feature importance display**: a simple horizontal bar list showing `get_feature_importance()` output — "here's what actually drove this prediction" — this is new, real, and answers your "what's affecting the dataset" question concretely
- Same options-considered and see-the-code sections as any other case

### Screen 5 — Results / skill map
- Final cleaned dataset preview (small table)
- The downstream-check chart (already built: `app/evaluation/downstream.py`)
- Skill map: list of concepts covered, all checked off
- Total XP, all badges earned, "Case Closed" if applicable

---

## 4. What's genuinely NOT built yet (be honest with judges about this)

- Multiple bundled example datasets (only one exists right now)
- Streaming/live reveal of cases as they're computed (current design computes everything, then reveals — genuinely fine for a hackathon demo, just not literally real-time)
- Classification support (regression only, by design — see architecture.md)
- Any actual Streamlit code — this document is the spec, not the implementation
