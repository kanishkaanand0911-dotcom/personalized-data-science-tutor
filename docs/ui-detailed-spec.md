# UI Spec — The Data Detective

*For Person C. This describes exactly what to build, screen by screen, and how to keep it from feeling cluttered even though there's genuinely a lot of content underneath.*

---

## 1. Identity & tone

**Concept:** every messy column is a "case" the agent investigates. This isn't decoration — it's the natural shape of the real backtrack behavior (try something → evidence contradicts it → switch → case closed), so the metaphor and the engineering line up honestly.

**Visual direction** (already prototyped and working — see `data_detective.html` from earlier in this project):
- **Colors:** deep ink-navy for text, a cool pale-sage paper background (not the generic cream/terracotta AI look), forest green for "verified/passed," warm amber for XP/rewards, muted rust only for "didn't work" states — used sparingly, never alarming
- **Type:** a serif for headings (journal/notebook feeling), a clean sans for body text
- **Tone:** calm, factual, never salesy. Failures are described plainly ("didn't work") not apologetically or dramatically

**The one rule that keeps this clean despite how much content exists underneath:** *progressive disclosure*. Every case shows three things by default — what was tried, why, what happened — and everything else (pros/cons of alternatives, the actual code, feature importance charts) lives behind an explicit "show more" toggle the user chooses to open. Nothing extra renders unless asked for.

---

## 2. Screen-by-screen

### Screen 1 — Choose your dataset
- Two clear paths, side by side: **"Try an example"** (shows the bundled dataset with a one-line description — "Sales data with messy dates, mixed-up cities, and missing deal values") or **"Upload your own CSV"**
- Upload path: drag-and-drop or file picker, basic validation feedback ("this doesn't look like a CSV" / "looks good — 350 rows, 8 columns")
- No practice-mode banner needed yet — that shows once real content starts

### Screen 2 — Pick your goal
- Practice-mode banner appears here for the first time, stays visible for the rest of the app: *"Practice mode — a learning walkthrough using example data, not a real business report"*
- Dataset's numeric columns shown as simple selectable cards (from `column_roles.py`'s auto-detection): **"What do you want to understand or predict?"**
- One line under each option explaining what it means in plain terms, not jargon (e.g. under "deal_value": *"See what drives how big or small a sale is"*)
- Deliberately NOT a free-text box — a dropdown/card picker is faster, and never misfires the way free-text goal parsing can

### Screen 3 — First look (EDA)
- Before any cleaning happens, one calm summary card: row/column count, what stands out (outliers, skew, correlations) — straight from `explore_dataset()` / `explain_eda()`
- This is the "a data scientist looks before touching anything" moment — genuinely new content, give it its own screen rather than burying it
- One small chart: a simple histogram of the target column's distribution (shows the skew mentioned in the text)

### Screen 4 — The case files (the core experience)
One case card per column issue, revealed one at a time (next case unlocks after the current one's quiz is answered):

**Always visible on the card:**
- Case number + concept tag ("Case 2 of 5 — Fixing inconsistent labels")
- Title ("The case of the many-named city")
- What was tried + why, in plain language
- If there was a retry: the failed attempt shown first and clearly marked, then the fix that worked — this is the actual adaptation moment, don't bury it
- The quiz: one question, immediate feedback, gentle re-explanation on a wrong answer (never punishing)
- XP earned + badge if one was unlocked, shown as a small toast/animation, not a blocking popup

**Behind a "Weigh the options" toggle (collapsed by default):**
- Every strategy the agent knows for this problem type, including ones it didn't need — each with a one-line pro and one-line con (`options_considered` from `lesson_builder.py`)
- This is where the "acts like a data scientist" feeling lives — but it's opt-in detail, not forced on everyone

**Behind a "See the code" toggle (collapsed by default):**
- The actual short code snippet + one-sentence explanation (`code_snippets.py`)
- Syntax-highlighted, small, monospace — clearly marked as real code, not prose

### Screen 5 — The model case (same card shape, extra content)
- Same structure as any case: what was tried, why, what happened, quiz
- **Feature importance chart**, always visible on this card (not hidden) since it directly answers "what's driving this" — a simple horizontal bar list from `get_feature_importance()`, e.g. "Account tier (Enterprise): 17%"
- **Overfitting note**, shown as a small reassuring line, not a warning unless it actually failed: *"The model performs almost the same on data it's seen and data it hasn't — a good sign it's not just memorizing."* (from the new `overfit_gap` check)
- **"Try it yourself" mini-tool**, behind a toggle: a few input fields matching the model's features, a "Predict" button, shows the result using `predict_new_row()`. If defaults were used for any field, say so plainly ("we filled in a typical value for city and sales rep since you didn't set them")

### Screen 6 — Case closed (summary)
- Final cleaned dataset preview (small table, first few rows)
- The downstream-check chart (aggregation/trend/chart already verified working)
- **Skill map**: checklist of concepts covered, all checked off, pulled from each case's `concept` field
- Total XP, every badge earned, "Case Closed" if the whole run resolved
- A closing line that's honest about scope, matching the practice-mode framing: *"This was a walkthrough with example data — the same steps apply to your own real data, with a real data scientist double-checking the details that matter for actual decisions."*

---

## 3. Full feature checklist

| Feature | Backend function it maps to | Where it shows |
|---|---|---|
| Dataset picker (example or upload) | — (new, UI-only) | Screen 1 |
| Goal / target column picker | `column_roles.auto_detect_feature_roles` | Screen 2 |
| Practice-mode banner | — (UI-only, persistent) | Screens 2–6 |
| First-look summary | `eda.explore_dataset`, `explain_eda` | Screen 3 |
| Cleaning cases with retry story | `agent.loop.run_agent`, `lesson_builder.build_cases` | Screen 4 |
| Comprehension quiz per case | `educator.quiz_generator.generate_quiz` | Screen 4, 5 |
| Pros/cons of all options | `lesson_builder` → `options_considered` | Screen 4, 5 (toggle) |
| Real code + explanation | `educator.code_snippets.get_code_snippet` | Screen 4, 5 (toggle) |
| XP + badges | `gamification.rules` | Screens 4–6 |
| Feature importance | `modeling.feature_importance.get_feature_importance` | Screen 5 |
| Overfitting check | `modeling.model_selector` → `overfit_gap` | Screen 5 |
| Try-it-yourself prediction | `modeling.model_selector.predict_new_row` | Screen 5 (toggle) |
| Downstream verification chart | `evaluation.downstream.run_downstream_checks` | Screen 6 |
| Skill map | derived from `cases[i]["concept"]` | Screen 6 |

---

## 4. What keeps this from feeling messy

1. **One primary action per screen.** Never two competing calls-to-action.
2. **Progressive disclosure everywhere.** Pros/cons, code, and the prediction tool are all opt-in — the default view is always the short, plain-language version.
3. **No raw stat dumps.** Every number the user sees already has a sentence around it explaining what it means (this is already how the backend formats everything — don't undo that by displaying raw JSON in the UI).
4. **Cases appear one at a time**, not all at once — reduces the page to "what's happening right now," not a wall of five cards.
5. **The practice-mode banner is calm, not alarming** — a colored strip with an info icon, not a warning triangle or a modal the user has to dismiss.
