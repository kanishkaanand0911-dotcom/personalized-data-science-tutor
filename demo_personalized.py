"""
End-to-end demo of the personalized multi-agent tutor.

Run it:
    python demo_personalized.py

No API key needed. With none set the platform runs its deterministic path and
says so; with GEMINI_API_KEY or ANTHROPIC_API_KEY set, the same pipeline runs
and the explanations are reworded by the model. Either way every number shown
is computed by pandas/scikit-learn on the real dataset.

The point of running two learners back to back is that the difference between
them is produced by the system, not scripted here: both go through the same
agents in the same order, and the role/level/goal in their opening sentence is
the only thing that differs.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import pandas as pd

from app.agent.loop import run_agent
from app.agents.orchestrator import Orchestrator
from app.core.config import settings
from app.core.state import StateStore
from app.llm.llm_client import llm_status

DATASET = os.path.join(PROJECT_ROOT, "data", "messy_sales_dataset.csv")


def banner(text: str, char: str = "=") -> None:
    print("\n" + char * 74)
    print(text)
    print(char * 74)


def show(label: str, result, limit: int = 1400) -> None:
    print(f"\n>>> {label}")
    print(f"    [intent: {result.intent} | agents: {', '.join(result.agents_called) or 'none'}]")
    message = result.message
    print("\n" + (message if len(message) <= limit else message[:limit] + "\n    ...[trimmed]"))


def run_learner(orchestrator: Orchestrator, user_id: str, opening: str,
                raw: pd.DataFrame, cleaned: pd.DataFrame, target: str,
                extra_questions: list[str]) -> None:
    banner(f"LEARNER: {user_id}", "=")
    print(f'They say: "{opening}"')

    # 1. PROFILE -- profiler agent extracts structure from that one sentence.
    show("Step 1 - Profiling", orchestrator.chat(user_id, opening))

    # 2. DATA -- data agent runs the original deterministic backend on their file.
    show("Step 2 - Analysing their dataset", orchestrator.upload_dataset(user_id, raw, target_col=target))

    # 3-4. LESSONS -- curriculum decided the order; teacher grounds each one in
    # their own data; quiz and practice come from the same facts.
    for i in (1, 2):
        result = orchestrator.next_lesson(user_id, df=cleaned)
        show(f"Step {2 + i} - Lesson {i}", result)

        quiz = next((r["data"]["quiz"] for r in result.responses if r["agent"] == "quiz_agent"), None)
        if quiz:
            show(f"       Answering the quiz correctly",
                 orchestrator.answer_quiz(user_id, quiz, quiz["correct_index"]))

        challenge = next((r["data"]["challenge"] for r in result.responses
                          if r["agent"] == "practice_agent"), None)
        if challenge and i == 1:
            # A deliberately thin answer, to show the evaluator marking down
            # and pushing the concept back into the learner's weak topics.
            show("       Submitting a weak answer on purpose",
                 orchestrator.submit_challenge(user_id, challenge, "I looked at it and it seemed fine"))

    # 5. FREE CONVERSATION -- the orchestrator routes each of these itself.
    for question in extra_questions:
        show(f'Step 5 - They ask: "{question}"', orchestrator.chat(user_id, question, df=cleaned))

    # 6. PROGRESS
    show("Step 6 - Progress", orchestrator.chat(user_id, "how am I doing"))


def main() -> None:
    banner("PERSONALIZED MULTI-AGENT DATA SCIENCE TUTOR", "#")
    status = llm_status()
    print(f"LLM provider: {status['provider']} ({status['mode']})")
    if not status["enabled"]:
        print("No API key set -- running the deterministic path. Every lesson below is still")
        print("grounded in real numbers computed from the dataset; only the wording is plainer.")

    settings.ensure_dirs()
    # A demo must start from zero XP every time, or the second run shows a
    # learner who has mysteriously already earned badges.
    store = StateStore(os.path.join(settings.state_dir, "demo"))
    for user in ("alex_sales", "sam_cleaner"):
        store.reset(user)
    orchestrator = Orchestrator(store=store)

    raw = pd.read_csv(DATASET)
    cleaned, _ = run_agent(raw, verbose=False)

    run_learner(
        orchestrator, "alex_sales",
        "My name is Alex. I am 20 years old. I work in sales. I am a complete beginner. "
        "I want to learn how to visualize my sales data.",
        raw, cleaned, "deal_value",
        ["which chart should I use to compare deal value across region?"],
    )

    run_learner(
        orchestrator, "sam_cleaner",
        "I'm Sam. I work with messy data every day and I want to learn data cleaning properly.",
        raw, cleaned, "deal_value",
        ["give me a challenge"],
    )

    # 7. THE COMPARISON -- the same platform, the same dataset, two different paths.
    banner("WHY THIS IS PERSONALIZATION, NOT ONE SHARED SCRIPT", "#")
    for user in ("alex_sales", "sam_cleaner"):
        state = store.load(user)
        profile, path = state["profile"], state["learning_path"]
        print(f"\n{user}: role={profile['role']}, level={profile['experience_level']}, "
              f"goal={profile['learning_goal']}")
        print("  path: " + " -> ".join(l["concept_key"] for l in path["lessons"]))
        progress = store.get_progress(user)
        print(f"  XP {progress.xp} (level {progress.level}) | badges: {', '.join(progress.badges) or 'none'}"
              f" | weak topics: {', '.join(progress.weak_topics) or 'none'}")

    print("\nSame dataset, same agents, same order of operations. The only input that")
    print("differed was the sentence each learner opened with.\n")


if __name__ == "__main__":
    main()
