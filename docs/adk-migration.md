# Migrating to Google ADK (`adk web`)

This document captures (1) the current system as it actually exists in this
repo today, and (2) a concrete plan for re-platforming it onto **Google's
Agent Development Kit (ADK)** so it can be launched and inspected with
`adk web`.

Nothing has been changed yet — this is the reference doc to work from.

---

## 1. What exists today

### 1.1 Tech stack

| Layer | Library | Notes |
|---|---|---|
| Web API | FastAPI + uvicorn | optional — demos run without it |
| Data / ML | pandas, numpy, scikit-learn | all deterministic facts + real regression models |
| Charts | matplotlib | renders PNGs to `data/charts/` |
| LLM (optional) | `google-genai` (Gemini) or `anthropic` | behind a provider-agnostic interface; `mock` provider is the no-key default |
| State | plain JSON files under `data/state/<user_id>.json` | via `app/core/state.py::StateStore` |
| Tests | pytest (86 tests), httpx (FastAPI TestClient) | all run offline |

There is **no existing dependency on Google ADK, LangChain, or any agent
framework** — "agents" here are plain Python classes with a shared base
class (`app/agents/base.py::Agent`), not an agent-framework construct.

### 1.2 Entry points

- `python demo_personalized.py` — scripted two-learner demo, no server.
- `python run_full_demo.py` — the original (pre-tutor) cleaning/modeling demo.
- `uvicorn app.main:app --reload` — FastAPI server exposing the orchestrator
  over 12 REST endpoints (`/onboard`, `/chat`, `/upload-data`, `/lesson/current`, …).
- `pytest -q` — the test suite.

There is currently **no chat UI** — `app/main.py` is the only interface
besides the two demo scripts, which is exactly the gap `adk web` fills.

### 1.3 The multi-agent system (`app/agents/`)

Nine specialist classes + one orchestrator, all subclassing `Agent`
(`app/agents/base.py`):

```python
class Agent(abc.ABC):
    name: str
    responsibility: str
    llm: BaseLLMClient          # lazily resolved singleton
    llm_enabled: bool
    def run(self, **kwargs) -> AgentResponse: ...   # abstract
```

| Agent (file) | Responsibility | LLM use |
|---|---|---|
| `orchestrator.py` | classify intent (keyword rules first, LLM fallback), route, assemble reply | fallback classifier only |
| `profiler_agent.py` | extract `UserProfile` from free text | fills only low-confidence fields |
| `data_agent.py` | wraps the ORIGINAL deterministic backend (`app/agent`, `app/eda`, `app/evaluation`, `app/modeling`) — stats, issue detection, cleaning loop, model selection | none — pure pandas/sklearn |
| `curriculum_agent.py` | build a `LearningPath` from profile+analysis+weak topics | none (deterministic rules) |
| `teacher_agent.py` | EXPLAIN → EXAMPLE (from real data) → CHECK for one lesson | reword-only, with deterministic template fallback |
| `visualization_agent.py` | pick + render a matplotlib chart | none |
| `quiz_agent.py` | one grounded MCQ; marks answers | reword-only |
| `practice_agent.py` | one open-ended task naming real columns | reword-only |
| `evaluator_agent.py` | score challenge answers, decide next difficulty, update weak/strong topics | none (keyword-coverage scoring) |
| `gamification_agent.py` | XP, levels, badges, streaks | none |

Every agent takes a **typed input** and returns a uniform envelope:

```python
@dataclass
class AgentResponse:
    agent: str
    intent: str
    message: str
    data: dict
    used_llm: bool
```

### 1.4 Orchestration logic (`app/agents/orchestrator.py`)

This is **not** an LLM-driven router. `Orchestrator.classify()` matches the
learner's text against a fixed keyword table (`INTENT_KEYWORDS`) covering
8 intents (`onboard`, `analyze_data`, `learn`, `visualize`, `quiz`,
`practice`, `progress`, `question`); only when nothing matches does it fall
back to an LLM classifier still constrained to the same 8-item enum.

Each intent then runs an **explicit, hardcoded pipeline** of agent calls,
e.g. `learn` → `curriculum → teacher → visualization (if chart lesson) →
quiz → practice → gamification`. This determinism is a stated design goal
(see README §4, §11) — "intent classification a person can read and predict
beats one that changes between runs."

### 1.5 State & session (`app/core/state.py`)

`StateStore` is a JSON-file-per-user store (`data/state/<user_id>.json`)
holding: `profile`, `progress` (XP/level/badges/streak/weak-strong topics),
`learning_path`, `dataset_analysis`. Reads/writes are lock-guarded and
atomic (`os.replace`). `Progress.weak_topics` is what closes the adaptive
loop — the evaluator writes to it, curriculum reads it back.

### 1.6 LLM provider abstraction (`app/llm/`)

```
app/llm/base_client.py   BaseLLMClient (abstract) + MockClient (returns None)
app/llm/llm_client.py    GeminiClient, AnthropicClient, get_llm_client() factory
app/llm/prompts.py       every system/user prompt template, one place
```

- `get_llm_client()` reads `app/core/config.py::settings` and returns a
  singleton — no agent ever imports a provider SDK or touches `os.environ`.
- `complete()` / `complete_json()` return `None` on **any** failure
  (missing key, rate limit, malformed JSON) — every caller already has a
  deterministic fallback, so the platform degrades gracefully rather than
  raising.
- Providers supported today: `gemini` (via `google-genai`), `anthropic`,
  `mock` (deterministic, default with no key set).

`app/core/config.py::Settings` resolves the provider from env vars
(`LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `ANTHROPIC_API_KEY`,
`ANTHROPIC_MODEL`, `STATE_DIR`, `UPLOAD_DIR`, `CHART_DIR`).

### 1.7 The preserved "original" deterministic core (`app/agent`, `app/actions`, `app/eda`, `app/evaluation`, `app/modeling`, `app/educator*`, `app/gamification`)

This is the pre-existing agentic **data-cleaning and model-selection loop**
(`OBSERVE → DECIDE → ACT → EVALUATE → ADAPT`, in `app/agent/loop.py` +
`app/agent/detect.py`) that the new tutor layer wraps rather than replaces.
It is 100% deterministic pandas/sklearn — no LLM involvement — and is what
gives every lesson its "real number from your file" grounding. It must
survive the ADK migration untouched; only the orchestration layer around it
changes.

### 1.8 API surface (`app/main.py`)

Thin FastAPI wrapper: 12 endpoints, each just calls into `Orchestrator` and
returns `.to_dict()`. No business logic lives here. This is the piece that
`adk web` effectively replaces/supplements as the interactive front end.

---

## 2. What Google ADK provides

ADK (`pip install google-adk`) is Google's Python framework for building,
orchestrating and locally serving LLM-powered agents. Relevant pieces:

- **`Agent` / `LlmAgent`** — an LLM-backed agent with a `name`, `model`
  (e.g. `"gemini-2.0-flash"`), `instruction` (system prompt), and `tools`
  (plain Python functions, auto-wrapped as `FunctionTool`s — docstring +
  type hints become the tool schema the model sees).
- **Multi-agent composition**:
  - `LlmAgent(sub_agents=[...])` — an LLM decides which sub-agent to
    delegate to (`transfer_to_agent`), analogous to our keyword router but
    LLM-driven instead of rule-driven.
  - `SequentialAgent`, `ParallelAgent`, `LoopAgent` — deterministic
    "workflow agents" that run children in a fixed order/parallel/loop
    *without* an LLM deciding the order. This is the closer match to our
    orchestrator's hardcoded pipelines (e.g. `learn` = curriculum → teacher
    → viz → quiz → practice → gamification, always in that order).
  - A custom `BaseAgent` subclass (`_run_async_impl`) for orchestration
    logic that's neither purely sequential nor purely LLM-delegated — this
    is the best fit for our **keyword-first, LLM-fallback** intent router.
- **Session & State** — `Session.state` is a dict scoped to a
  `(app_name, user_id, session_id)`, backed by an injectable
  `SessionService` (in-memory for dev, or a persistent one). Tools/agents
  read and write it via `ToolContext.state` / `CallbackContext.state`.
  Keys prefixed `user:` persist across sessions for the same user; `app:`
  is global; unprefixed is session-scoped.
- **Tools** — any typed, docstring'd Python function becomes a callable
  tool for an `LlmAgent`. Return a `dict` (ADK wraps non-dict returns).
- **`adk web`** — a local dev UI (chat window + trace/event inspector +
  session state viewer) that auto-discovers agents from a folder
  structure:

  ```
  parent_dir/
    my_agent/
      __init__.py     # from . import agent
      agent.py        # must define `root_agent = ...`
      .env            # GOOGLE_API_KEY=... (or Vertex AI creds)
  ```

  Run `adk web` from `parent_dir`; it lists every subfolder with a
  `root_agent` in the browser's agent picker.

- **Model support** — first-class Gemini (API key or Vertex AI); other
  models (Anthropic, etc.) via `LiteLlm` wrapper
  (`google.adk.models.lite_llm.LiteLlm(model="anthropic/claude-...")`), so
  our existing Anthropic option is not lost, just re-wired.

---

## 3. Mapping this codebase onto ADK

### 3.1 High-level shape

```
personalized-data-science-tutor/
  tutor_agent/                       <- new ADK app folder (adk web root)
    __init__.py                      # from . import agent
    agent.py                         # defines root_agent
    sub_agents/
      profiler.py                    # LlmAgent, instruction ~= profiler_agent.py's prompt
      data_analyst.py                # LlmAgent whose tools call app/agents/data_agent.py
      curriculum.py                  # LlmAgent or plain function tool (fully deterministic today)
      teacher.py                     # LlmAgent, tools expose _facts_for() as a tool
      visualization.py               # LlmAgent, tool wraps app/visualization/charts.py
      quiz.py / practice.py / evaluator.py / gamification.py  # same pattern
    tools/
      data_tools.py                  # FunctionTool wrappers over app/agents/data_agent.py
      state_tools.py                 # read/write StateStore-equivalent via ToolContext.state
    .env                             # GOOGLE_API_KEY / GEMINI_MODEL etc.
  app/                                # UNCHANGED — all deterministic logic stays here
    agent/ actions/ eda/ evaluation/ modeling/ ...
    core/ llm/ personalization/ visualization/
  ...
```

Key principle: **keep `app/` exactly as-is as the deterministic engine**,
and build a thin ADK layer on top that calls into it via tools. This
matches the project's own stated philosophy ("the LLM rewords facts Python
already computed") and minimizes risk to the 86 existing tests.

### 3.2 Orchestrator → ADK custom `BaseAgent`

The orchestrator's rule-first/LLM-fallback classification and its
per-intent hardcoded pipelines don't map cleanly onto `LlmAgent` delegation
(which is inherently LLM-decided) or a pure `SequentialAgent` (which is
always-fixed-order with no branching). The best fit:

```python
from google.adk.agents import BaseAgent

class TutorOrchestrator(BaseAgent):
    async def _run_async_impl(self, ctx):
        intent, reason, used_llm = classify(ctx.user_content.text)  # reuse existing classify()
        pipeline = PIPELINES[intent]        # e.g. [curriculum, teacher, visualization, quiz, practice, gamification]
        for sub_agent in pipeline:
            async for event in sub_agent.run_async(ctx):
                yield event
```

This preserves the *exact* keyword-routing behavior and readable, testable
pipelines while still being a proper ADK agent that `adk web` can host and
trace. `classify()` and `INTENT_KEYWORDS` move verbatim from
`orchestrator.py`.

### 3.3 Deterministic agents → tools, not `LlmAgent`s

Agents that do zero LLM work today (`data_agent`, `curriculum_agent`,
`visualization_agent`, `evaluator_agent`, `gamification_agent`,
quiz-marking) should **not** become `LlmAgent`s — wrapping a deterministic
pandas computation in a model call would add latency, cost, and a source of
hallucinated numbers, directly against the project's core invariant
("every number is real"). Instead, expose their existing public methods as
plain **FunctionTools**:

```python
def analyze_dataset(csv_path: str, target_col: str | None = None) -> dict:
    """Analyze the learner's uploaded CSV: structure, quality issues, EDA,
    cleaning log, and (if target_col given) a selected regression model.
    """
    df = pd.read_csv(csv_path)
    return DataAgent().analyze(df, target_col=target_col).to_dict()
```

A thin `LlmAgent` (e.g. "Data Analyst Agent") can sit in front of this tool
purely to narrate/route, while the tool itself guarantees every figure
still comes from `app/agents/data_agent.py` unmodified.

### 3.4 LLM-reword agents → `LlmAgent` with fallback tool

`teacher_agent`, `quiz_agent`, `practice_agent` already have exactly the
shape ADK wants: a deterministic "facts" step + an optional LLM rewording
step. Map each to an `LlmAgent` whose **instruction** is the existing
`TEACHER_SYSTEM`/`TEACHER_USER` template (`app/llm/prompts.py`) and whose
**tool** is `_facts_for()` (already pure, already returns grounded
strings). The deterministic `_deterministic_block()` template path becomes
the no-API-key fallback exactly as it works today — ADK doesn't need to
own that fallback; keep it in `app/agents/teacher_agent.py` and only call
into ADK's `LlmAgent` when `settings.llm_enabled()` is true, else keep
calling the existing deterministic method directly. This lets `adk web`
run in both LLM and offline mode, matching the current design goal.

### 3.5 State: `StateStore` (JSON) vs ADK `Session.state`

Two viable approaches, in order of recommended effort:

1. **Keep `StateStore` as the durable store, mirror into session state.**
   At the start of each ADK turn, load `StateStore.load(user_id)` into
   `ctx.session.state` (prefixed `user:profile`, `user:progress`,
   `user:learning_path`, `user:dataset_analysis`); at the end, persist any
   mutated keys back via `StateStore.update()`. This changes nothing about
   `app/core/state.py` and keeps `tests/test_core.py` / existing JSON files
   working.
2. **Full replacement**: implement a custom ADK `SessionService` backed by
   the same per-user JSON files, so ADK's own session lifecycle (used by
   `adk web`'s session picker) is the single source of truth. More
   idiomatic long-term, more work up front — worth doing once the tutor is
   stable, not as the first migration step.

Start with (1).

### 3.6 LLM provider: keep `app/llm/` or switch to ADK's model layer?

Two options:

- **A — ADK owns the model call.** `LlmAgent(model="gemini-2.0-flash", ...)`
  for Gemini, `LlmAgent(model=LiteLlm(model="anthropic/claude-sonnet-4-5"))`
  for Anthropic. Simpler, idiomatic ADK, but the "returns `None` on any
  failure, caller always has a fallback" contract (`BaseLLMClient`) would
  need to be re-implemented as ADK callbacks (`before_model_callback` /
  `after_model_callback` or a try/except around `run_async`).
- **B — Keep `app/llm/llm_client.py` as-is**, and call it *inside* a
  `FunctionTool` that an `LlmAgent`'s outer wrapper invokes, rather than
  using ADK's native model dispatch for the reword step. Preserves 100% of
  existing fallback semantics and tests, at the cost of not using ADK's
  model layer "for real" (i.e. the ADK agent would mostly be a thin shell
  around a tool call rather than doing genuine LLM reasoning).

**Recommendation:** use **A** for the actual conversational agents (this is
the point of adopting ADK — a real LLM decides phrasing/routing nuance and
you get tracing/session UI for free), but retain `app/llm/prompts.py`
verbatim as the instruction text so prompt engineering already done isn't
lost. Keep `MockClient`-equivalent behavior by giving `adk web` a
`.env` with no key → document that ADK's Gemini agents require a key
(unlike today's mock fallback), and keep the pure-Python deterministic
agents (§3.3) as the true "no API key" path exposed instead via a
non-ADK CLI/pytest path, OR gate `root_agent` construction so that with no
`GOOGLE_API_KEY` set, the orchestrator wires the deterministic
`TeacherAgent`/`QuizAgent` methods directly instead of constructing
`LlmAgent`s pointed at Gemini.

### 3.7 Charts and file upload

`adk web`'s chat UI supports rendering artifacts/attachments. Uploading a
CSV maps to ADK's artifact service (`ctx.save_artifact(...)`) or, more
simply for a first pass, a `FunctionTool` parameter that takes a file path
the user pastes/uploads via the UI's attachment control, then calls the
existing `_frame_for()` / `analyze()` path unchanged. Rendered chart PNGs
(`app/visualization/charts.py`) can be returned as ADK artifacts so they
render inline in `adk web` instead of needing the `/chart` FastAPI route.

### 3.8 What stays completely untouched

- `app/agent/`, `app/actions/`, `app/eda/`, `app/evaluation/`,
  `app/modeling/` — the original cleaning/modeling loop. Zero ADK
  awareness needed; called only via tools.
- `app/core/schemas.py` — dataclasses stay as the internal data contracts;
  tool functions just call `.to_dict()` at the ADK boundary.
- `app/personalization/learning_path.py`, `profile_extractor.py` — pure
  rule engines, wrapped as tools, not rewritten.
- All 86 existing tests — none of them import FastAPI's app in a way that
  ADK migration should break, since `app/main.py` can remain as a parallel,
  optional interface.

---

## 4. Concrete migration steps (suggested order)

1. `pip install google-adk` (and `pip install google-adk[a2a]`/`litellm` if
   Anthropic support is wanted) — add to `requirements.txt` as an optional
   extra, same convention as the existing FastAPI/LLM sections.
2. Create the `tutor_agent/` package skeleton (see §3.1) with a
   **minimal** `root_agent` that is just `TutorOrchestrator` (custom
   `BaseAgent`) delegating to one placeholder sub-agent, and confirm
   `adk web` discovers and runs it end-to-end (`adk web` from the repo
   root, or from whatever parent directory contains `tutor_agent/`).
3. Wrap `DataAgent.analyze` / `.summarize` as tools; wire the
   `analyze_data` pipeline first, since it has no LLM dependency and is
   the easiest to verify (numbers must match `tests/test_agents.py`
   exactly).
4. Port `curriculum_agent`, `visualization_agent`, `evaluator_agent`,
   `gamification_agent`, and quiz-marking as tools, following the same
   pattern.
5. Port `teacher_agent`, `quiz_agent`, `practice_agent` as `LlmAgent`s
   using the existing prompt templates from `app/llm/prompts.py`, with the
   deterministic methods kept as an explicit no-key fallback path.
6. Wire `profiler_agent` — likely the best candidate to be a "real"
   `LlmAgent` first, since profile extraction already tolerates an LLM
   filling gaps the rules didn't catch.
7. Implement the `StateStore` ↔ `Session.state` bridge (§3.5, option 1).
8. Reproduce the orchestrator's per-intent pipelines inside
   `TutorOrchestrator._run_async_impl`, intent by intent, checking against
   `tests/test_agents.py`'s routing assertions as a spec.
9. Manually exercise the full learner journey in `adk web`'s chat UI
   (onboard → upload CSV → lesson → quiz → progress) and compare output
   against `demo_personalized.py`'s recorded transcript.
10. Decide whether `app/main.py` (FastAPI) is kept as a second interface or
    retired in favor of `adk web` / ADK's own API server (`adk api_server`
    exposes a REST surface too, if the FastAPI-specific `/chart`
    path-traversal-guarded endpoint isn't needed).

---

## 5. Open questions to resolve before/while implementing

- **Anthropic support**: keep it via `LiteLlm`, or drop it and standardize
  on Gemini now that ADK is Google's own framework? (Affects whether
  `app/educator_anthropic_backup/` and `AnthropicClient` need porting.)
- **No-API-key mode**: `adk web` assumes a working model; decide whether
  "deterministic mode" remains a first-class supported mode post-migration
  (recommended, per README's stated invariant) or becomes a secondary
  fallback only reachable outside `adk web`.
- **Multi-user / session semantics**: ADK's session model
  (`app_name/user_id/session_id`) is richer than the current single
  `user_id` JSON file — decide if `session_id` should map 1:1 to today's
  `user_id`, or if the tutor should support multiple concurrent learning
  sessions per user.
