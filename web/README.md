# web/ - the learning app

A thin FastAPI layer around the existing agentic backend in `app/`, plus a
single-page frontend that turns each agent decision into a Duolingo-style level.

This layer makes **no** cleaning or modeling decisions. It calls `run_agent`,
the downstream checks, `select_and_fit_model`, and `generate_lesson`, then shapes
their output for the screens. A learner's guess is scored but never feeds back
into the pipeline.

## Run it

```bash
pip install -r requirements.txt
python run_web.py                 # http://127.0.0.1:8000
python run_web.py --port 9000 --reload
```

Optional: set `GEMINI_API_KEY` in `.env` for LLM-worded lesson text. Without it
the lesson uses deterministic wording built from the agent's own `reason`
strings. The pipeline never depends on the key.

## Files

| File | Role |
|---|---|
| `api.py` | FastAPI routes, in-memory sessions, static serving |
| `pipeline.py` | sequences `app/` into one run, shapes output, generic column detection for arbitrary CSVs |
| `copy.py` | friendly strategy names, role-flavored analogies, `plain()` sanitizer |
| `static/` | `index.html`, `styles.css`, `app.js`, `assets/mascot.svg` |

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/session` | start a session, store `{role, experience}` |
| GET | `/api/session/state` | rehydrate a reloaded client |
| POST | `/api/dataset` | upload a CSV or `use_sample=true`; runs detection + full pipeline |
| POST | `/api/levels/{id}/guess` | lock a guess, return the agent's real attempts for that column |
| GET | `/api/verify` | downstream check results |
| GET | `/api/model` | model-selection observation, attempts, chosen model |
| GET | `/api/results` | cleaned preview, columns changed, model, score, lesson |

The `/api/dataset` response and `/api/levels` never include attempt outcomes.
Outcomes are only returned by `/api/levels/{id}/guess`, after a guess is locked.

## Personalization

Two separate axes, deliberately not conflated:

- **Roadmap and levels** are data-driven, from `detect_issues()` on the loaded
  dataset. Different data gives a different path.
- **Role** (sales, operations, hr, student, or a custom word) only changes the
  flavor of the analogy text on each level. It never changes detection,
  strategy order, thresholds, or the agent's decision.

## Design

Visual direction is in `../DESIGN.md` (Berry Bright palette, Bricolage Grotesque
+ Manrope, custom mascot). The anti-slop skill in `.claude/skills/` is the filter
on top. Product name is a placeholder (`Data Agent`) in one constant per file.

## 21st.dev

`../.mcp.json` has a `21st` remote MCP server entry (`.mcp.json` is gitignored
because it holds the key):

1. Get a key at <https://21st.dev/mcp> (AI generation tools only appear if AI
   access is enabled on the account).
2. Replace `PASTE_YOUR_21ST_DEV_API_KEY_HERE` in `../.mcp.json`.
3. Reload the project. Claude Code / the desktop Code tab prompts to approve the
   project MCP server; approve it.

`/plugin` is not available in the desktop Code tab, so the plugin-marketplace
route needs the `claude` CLI. The `.mcp.json` route above works in the Code tab.

Without the server, the manual flow still works: copy a component's prompt from
21st.dev and build it against the `DESIGN.md` tokens.
