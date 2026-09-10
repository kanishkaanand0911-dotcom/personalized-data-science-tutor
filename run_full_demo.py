"""
Full end-to-end walkthrough: raw messy data -> cleaning (with backtrack) ->
downstream verification -> model selection -> plain-language lesson.

Just run:
    python run_full_demo.py

No need to be in any particular folder first -- this script finds its own
location and sets everything up relative to that, so it works the same
whether you run it from the project folder itself or from anywhere else.
"""

import os
import sys

# Find this script's own folder, and set up imports relative to THAT --
# not to any hardcoded path. This is what makes the script portable
# across different computers/folders.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app", "educator"))  # narrate_llm.py imports `schemas` directly

# Load .env into the actual process environment -- without this, a .env
# file with a real key in it is invisible to os.environ.get(), which is
# what call_llm() checks. This is what actually connects your .env file
# to the code.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    print("NOTE: python-dotenv isn't installed, so .env won't be read automatically.")
    print("Run: pip install python-dotenv\n")

import pandas as pd
from app.agent.loop import run_agent
from app.evaluation.downstream import run_downstream_checks
from app.modeling.model_selector import select_and_fit_model
from schemas import ActionLogEntry, ModelLogEntry
from narrate_llm import generate_lesson


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------- 0. The raw, messy data a user would upload ----------
section("STEP 0 - What the user uploads (raw, messy)")
csv_path = os.path.join(PROJECT_ROOT, "data", "messy_sales_dataset.csv")
df = pd.read_csv(csv_path)
print(df.head(6).to_string())
print(f"\n... {len(df)} rows total")
print(f"Missing deal_value: {df['deal_value'].isna().sum()} rows")
print(f"Distinct raw city spellings: {df['city'].nunique()}")


# ---------- 0b. Explore before touching anything ----------
section("STEP 0b - Exploring the raw data first (EDA)")
from app.eda.explore import explore_dataset, explain_eda
eda = explore_dataset(df, target_col="deal_value")
print(explain_eda(eda))


# ---------- 1. Cleaning loop, with backtracking ----------
section("STEP 1 - Agent cleans the data (observe -> act -> evaluate -> adapt)")
cleaned_df, action_log = run_agent(df, verbose=True)


# ---------- 2. Downstream verification ----------
section("STEP 2 - Agent checks the cleaned data actually WORKS")
downstream_result = run_downstream_checks(
    cleaned_df, group_col="region", numeric_col="deal_value", date_col="signup_date"
)
for c in downstream_result["checks"]:
    status = "PASS" if c["passed"] else "FAIL"
    print(f"[{status}] {c['check']}: {c['reason']}")
print(f"\nOverall: {'PASSED' if downstream_result['overall_passed'] else 'FAILED'}")


# ---------- 3. Model selection ----------
section("STEP 3 - Agent picks a model (observe -> decide -> act -> evaluate -> adapt)")
cleaned_df["signup_month"] = cleaned_df["signup_date"].dt.month
model_result = select_and_fit_model(
    cleaned_df, target_col="deal_value",
    feature_cols=["region", "city", "sales_rep", "signup_month", "account_tier"],
    numeric_cols=["signup_month"],
    categorical_cols=["region", "city", "sales_rep", "account_tier"],
)
print("Observed data shape:", model_result["observation"])
print(f"\nDecision: {model_result['start_reason']}\n")
for entry in model_result["model_log"]:
    status = "PASSED" if entry["passed"] else "FAILED (escalating)"
    print(f"[{entry['model_tried']}] {status} -- {entry['reason']}")
chosen_name = model_result['chosen_model']['name'] if model_result['chosen_model'] else 'NONE -- flagged for human review'
print(f"\nFinal model chosen: {chosen_name}")


# ---------- 4. What the actual end user sees ----------
section("STEP 4 - What a NON-TECHNICAL USER actually sees (the educator layer)")
if os.environ.get("GEMINI_API_KEY"):
    print("(GEMINI_API_KEY is set -- this should be real LLM narration)\n")
else:
    print("(No GEMINI_API_KEY found -- showing fallback template text, not real LLM output)\n")

action_entries = [ActionLogEntry(**e) for e in action_log]
model_entries = [ModelLogEntry(**e) for e in model_result["model_log"]]
lesson = generate_lesson(action_entries, model_entries)
print(lesson)


# ---------- 4b. The "Data Detective" lesson + quiz layer ----------
section("STEP 4b - Cases, quizzes, and badges (the Duolingo-style layer)")
sys.path.insert(0, os.path.join(PROJECT_ROOT, "app", "gamification"))
from app.educator.lesson_builder import build_cases
from quiz_generator import generate_quiz
from rules import badge_for_case, final_badge, XP_RULES

cases = build_cases(action_log, model_result["model_log"], model_result.get("all_candidates_considered"))
total_xp = 0
for case in cases:
    print(f"\n[{case['concept']}] {case['title']}")
    for a in case["attempts"]:
        status = "PASS" if a["passed"] else "FAIL"
        print(f"  {status} tried {a['action_tried']} -- why: {a['why_tried']}")
    quiz = generate_quiz(case)
    print(f"  Quiz: {quiz['q']}")
    for i, opt in enumerate(quiz["options"]):
        marker = " <- correct" if i == quiz["correct"] else ""
        print(f"    {i}. {opt}{marker}")
    badge = badge_for_case(case)
    if badge:
        print(f"  Badge earned: {badge}")
    total_xp += XP_RULES["case_viewed"] + XP_RULES["quiz_correct_first_try"]

fb = final_badge(cases)
print(f"\nFinal badge: {fb if fb else '(not all cases resolved)'}")
print(f"Total XP (if every quiz answered correctly first try): {total_xp}")


# ---------- 5. Final cleaned output ----------
section("STEP 5 - Final cleaned dataset (what actually changed)")
print(cleaned_df[["deal_value", "city", "signup_date", "revenue_display", "account_tier"]].head(6).to_string())
