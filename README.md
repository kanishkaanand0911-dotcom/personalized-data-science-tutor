# AutoTriage-Clean: An Agentic Data Cleaning & Modeling Educator

An AI agent that cleans a user's own messy dataset, verifies its work actually holds up, picks an appropriate ML model for it, and explains every decision in plain language — built for people with zero data science background.

## The problem

Non-technical professionals (sales, ops, HR) have real data they want to understand, but existing options are two extremes: generic DS courses using textbook datasets, or nothing at all. People end up avoiding their own data, outsourcing it, or fumbling through it without real understanding.

## Why this needs to be an agent, not a script or a chatbot

A fixed cleaning script applies one rule per problem and hopes for the best. An LLM chatbot can describe cleaning steps but has no mechanism to check whether its own actions actually worked. This system does neither — it:

1. **Observes** the data and detects real problems
2. **Decides** which fix to try first
3. **Acts** — applies the fix
4. **Evaluates** — re-inspects the data afterward against statistical thresholds
5. **Adapts** — if the fix failed the check, it's discarded and a more sophisticated strategy is tried instead

The same loop runs a second time for model selection.

## Architecture

```
User uploads dataset
      ↓
detect_issues → decision tree → action_fn
      ↑                           ↓
      └──── evaluation ← compute_stats
      ↓
downstream_check → model_selector → educator/narrate
```

## Component breakdown

| Component | What it does | Type |
|---|---|---|
| detect_issues | Scans columns, classifies problems | Deterministic |
| Decision tree | Orders candidate fixes | Deterministic |
| Action functions | Apply fixes | Deterministic |
| Evaluation | Checks whether fixes worked | Statistical |
| downstream_check | Verifies usability | Deterministic |
| model_selector | Picks and validates regression models | sklearn |
| educator/narrate | Explains decisions | LLM + fallback |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
```

## Running

```bash
python run_full_demo.py
```

Without an API key, narration falls back to deterministic template text automatically.

## Current limitations

- Fuzzy matching uses `difflib`.
- Alias mapping is partly manual.
- Model selection currently supports regression models.
- The downstream check currently runs once after cleaning.

## Team

- **Person A** — agentic core
- **Person B** — LLM narration layer
- **Person C** — UI, dataset preparation, documentation, demo script
