"""Web-layer tests. The one that matters most: a learner's guess is scored but
never changes the agent's real pipeline output.

Run with `pytest tests/test_web.py -v` from the project root, or standalone:
`python tests/test_web.py`.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "educator"))

# Pin the optional ADK tutor connector to an address nothing listens on, so
# these tests stay deterministic regardless of whether a real `adk api_server`
# happens to be running on this machine - web/chat.py must read this before
# it's imported.
os.environ.setdefault("ADK_BASE_URL", "http://127.0.0.1:1")

import pandas as pd
from fastapi.testclient import TestClient

from web import pipeline
from web.api import app

client = TestClient(app)
SAMPLE = ROOT / "data" / "messy_sales_dataset.csv"


def _session(role="sales", experience="New to this"):
    sid = client.post("/api/session", json={"role": role, "experience": experience}).json()["session_id"]
    return {"X-Session-Id": sid}


def _load_sample(headers):
    return client.post("/api/dataset", headers=headers, data={"use_sample": "true"})


def test_health():
    assert client.get("/api/health").json()["ok"] is True


def test_dataset_produces_data_driven_levels():
    h = _session()
    body = _load_sample(h).json()
    cols = [lvl["column"] for lvl in body["levels"]]
    assert cols == ["deal_value", "city", "signup_date", "revenue_display"]
    assert body["levels"][0]["guess_kind"] == "which_strategy"
    # outcomes must not leak into the pre-guess payload
    assert "passed" not in str(body["levels"])


def test_guess_does_not_change_pipeline_output():
    """The core guarantee. A right guess and a wrong guess on the same dataset
    must yield byte-identical agent attempts."""
    h1, h2 = _session(), _session()
    _load_sample(h1)
    _load_sample(h2)

    right = client.post("/api/levels/0/guess", headers=h1, json={"choice_id": "impute_knn"}).json()
    wrong = client.post("/api/levels/0/guess", headers=h2, json={"choice_id": "impute_median"}).json()

    assert right["correct"] is True and right["points_awarded"] == pipeline.GUESS_CORRECT_POINTS
    assert wrong["correct"] is False and wrong["points_awarded"] == pipeline.GUESS_WRONG_POINTS
    assert right["agent_choice"] == wrong["agent_choice"] == "impute_knn"
    assert right["attempts"] == wrong["attempts"]  # identical agent behavior


def test_guess_is_locked_after_first_submit():
    h = _session()
    _load_sample(h)
    first = client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_median"}).json()
    second = client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_knn"}).json()
    assert first["correct"] is False
    assert second["correct"] is False  # not rescored
    assert second["locked"] is True
    assert second["your_choice"] == "impute_median"


def test_quiz_is_grounded_and_does_not_leak_the_answer():
    h = _session()
    _load_sample(h)
    client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_knn"})

    quiz = client.get("/api/levels/0/quiz", headers=h).json()
    assert len(quiz["questions"]) == 2
    assert "deal_value" in quiz["questions"][0]["prompt"]
    assert "answer" not in str(quiz["questions"])  # never ships the correct option


def test_quiz_scores_and_is_locked_after_first_submit():
    h = _session()
    _load_sample(h)
    client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_knn"})
    quiz = client.get("/api/levels/0/quiz", headers=h).json()["questions"]

    all_wrong = {q["id"]: "__definitely_not_an_option__" for q in quiz}
    first = client.post("/api/levels/0/quiz", headers=h, json={"answers": all_wrong}).json()
    assert first["points_awarded"] == len(quiz) * pipeline.QUIZ_WRONG_POINTS
    assert all(v is False for v in first["results"].values())

    second = client.post(
        "/api/levels/0/quiz", headers=h, json={"answers": {q["id"]: q["options"][0] for q in quiz}}
    ).json()
    assert second["points_awarded"] == first["points_awarded"]  # locked, not rescored


def test_quiz_only_scores_the_question_actually_answered():
    """A flashcard only ever submits one of a level's two real questions -
    the other one must not be silently graded as wrong."""
    h = _session()
    _load_sample(h)
    client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_knn"})
    quiz = client.get("/api/levels/0/quiz", headers=h).json()["questions"]
    assert len(quiz) == 2

    only_first = {quiz[0]["id"]: "__wrong_on_purpose__"}
    result = client.post("/api/levels/0/quiz", headers=h, json={"answers": only_first}).json()
    assert result["points_awarded"] == pipeline.QUIZ_WRONG_POINTS
    assert list(result["results"].keys()) == [quiz[0]["id"]]


def test_quiz_points_count_toward_total():
    h = _session()
    _load_sample(h)
    client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_knn"})
    quiz = client.get("/api/levels/0/quiz", headers=h).json()["questions"]
    correct_answers = client.post(
        "/api/levels/0/quiz", headers=h, json={"answers": {q["id"]: "__wrong__" for q in quiz}}
    ).json()["correct_answers"]

    h2 = _session()
    _load_sample(h2)
    client.post("/api/levels/0/guess", headers=h2, json={"choice_id": "impute_knn"})
    result = client.post("/api/levels/0/quiz", headers=h2, json={"answers": correct_answers}).json()
    assert result["points_awarded"] == 2 * pipeline.QUIZ_CORRECT_POINTS
    assert result["points_total"] == pipeline.GUESS_CORRECT_POINTS + 2 * pipeline.QUIZ_CORRECT_POINTS


def test_plain_reason_removes_statistics_jargon_but_keeps_every_number():
    from web.copy import plain_reason

    fail = plain_reason(
        "skew shifted 21.3% (2.186 -> 2.651), exceeds 15.0% threshold -- distribution distorted"
    )
    assert "21.3%" in fail
    assert "skew" not in fail.lower()
    assert "threshold" not in fail.lower()

    ok = plain_reason("skew shift 7.6%, within 15.0% threshold")
    assert "7.6%" in ok
    assert "skew" not in ok.lower()

    model_fail = plain_reason(
        "cross-validated R^2 = 0.41 is below the 0.5 minimum -- model isn't explaining enough variance"
    )
    assert "0.41" in model_fail
    assert "R^2" not in model_fail

    # an unrecognized reason (e.g. a future change to app/) still comes back
    # readable instead of erroring
    assert plain_reason("some new reason with a 42% figure") == "Some new reason with a 42% figure"


def test_level_code_shows_the_real_kept_strategy():
    h = _session()
    _load_sample(h)
    client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_knn"})
    code = client.get("/api/levels/0/code", headers=h).json()
    assert code["available"] is True
    assert code["label"] == "Nearest-neighbor fill"
    assert "KNNImputer" in code["code"]
    assert code["explain"]


def test_model_code_shows_the_real_chosen_model():
    h = _session()
    _load_sample(h)
    code = client.get("/api/model/code", headers=h).json()
    assert code["available"] is True
    assert code["code"]
    assert code["explain"]


def test_model_quiz_is_grounded_in_the_real_chosen_model():
    h = _session()
    _load_sample(h)
    quiz = client.get("/api/model/quiz", headers=h).json()["questions"]
    assert len(quiz) == 2
    assert quiz[0]["id"] == "model_chosen"
    assert "answer" not in str(quiz)


def test_model_quiz_scores_and_is_locked_after_first_submit():
    h = _session()
    _load_sample(h)
    quiz = client.get("/api/model/quiz", headers=h).json()["questions"]

    all_wrong = {q["id"]: "__nope__" for q in quiz}
    first = client.post("/api/model/quiz", headers=h, json={"answers": all_wrong}).json()
    assert first["points_awarded"] == len(quiz) * pipeline.QUIZ_WRONG_POINTS

    second = client.post("/api/model/quiz", headers=h, json={"answers": first["correct_answers"]}).json()
    assert second["points_awarded"] == first["points_awarded"]  # locked, not rescored


def test_canonical_backtrack_example_is_intact():
    h = _session()
    _load_sample(h)
    reveal = client.post("/api/levels/0/guess", headers=h, json={"choice_id": "impute_knn"}).json()
    labels = [(a["label"], a["passed"]) for a in reveal["attempts"]]
    assert labels[0][1] is False and "21.3%" in reveal["attempts"][0]["reason"]
    assert labels[1][1] is True and "7.6%" in reveal["attempts"][1]["reason"]


def test_full_flow_reaches_results():
    h = _session()
    _load_sample(h)
    for i in range(4):
        client.post(f"/api/levels/{i}/guess", headers=h, json={"choice_id": "pass"})
    assert client.get("/api/verify", headers=h).json()["overall_passed"] is True
    assert client.get("/api/model", headers=h).json()["available"] is True
    res = client.get("/api/results", headers=h).json()
    assert res["levels_total"] == 4
    assert res["downstream_passed"] is True
    assert "## " in res["lesson"]


def test_no_session_is_rejected():
    assert client.get("/api/verify").status_code == 401


def test_visualize_returns_real_charts_from_the_cleaned_data():
    h = _session()
    _load_sample(h)
    data = client.get("/api/visualize", headers=h).json()

    assert len(data["numeric_charts"]) > 0
    numeric = data["numeric_charts"][0]
    assert numeric["column"]
    assert len(numeric["bars"]) > 0
    assert sum(b["value"] for b in numeric["bars"]) > 0

    assert len(data["category_charts"]) > 0
    category = data["category_charts"][0]
    assert category["column"]
    assert len(category["bars"]) > 0

    # the sample dataset has a real date + numeric column, so a trend must
    # actually be computed, not just left null
    assert data["trend_chart"] is not None
    assert len(data["trend_chart"]["points"]) >= 2


def test_visualize_requires_a_loaded_dataset():
    h = _session()
    assert client.get("/api/visualize", headers=h).status_code == 409


def test_chat_falls_back_honestly_without_an_api_key():
    h = _session()
    _load_sample(h)
    r = client.post("/api/chat", headers=h, json={"message": "what is a missing value?", "level_id": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is False
    assert "reply" in body and len(body["reply"]) > 0


def test_chat_gives_a_real_faq_answer_instead_of_a_dead_end():
    """The single most common thing a curious learner does when no live
    model is connected: ask a real question. That must not just apologize."""
    h = _session()
    _load_sample(h)
    r = client.post(
        "/api/chat",
        headers=h,
        json={"message": "why not just delete the rows with missing values?", "level_id": 0},
    )
    body = r.json()
    assert body["grounded"] is False
    assert "deal_value" in body["reply"]  # grounded in the real column being studied
    assert "ask whoever's running the demo" not in body["reply"]
    assert len(body["reply"]) > 80  # a real explanation, not a one-line refusal


def test_faq_fallback_matches_several_common_questions():
    from web import chat as chatbot

    assert chatbot._faq_fallback("what is skew anyway?", None) is not None
    assert chatbot._faq_fallback("what's R2 mean", None) is not None
    assert chatbot._faq_fallback("how does the agent decide what to keep", None) is not None
    assert chatbot._faq_fallback("completely unrelated gibberish question", None) is None


def test_adk_extract_text_skips_tool_events_and_takes_the_last_reply():
    from web import chat as chatbot

    events = [
        {"content": {"parts": [{"functionCall": {"name": "chat_with_tutor"}}]}},
        {"content": {"parts": [{"functionResponse": {"name": "chat_with_tutor"}}]}},
        {"content": {"parts": [{"text": "Here's the real reply."}]}},
    ]
    assert chatbot._adk_extract_text(events) == "Here's the real reply."
    assert chatbot._adk_extract_text([{"content": {"parts": []}}]) is None


def test_adk_extract_tool_result_returns_the_structured_profile_and_progress():
    from web import chat as chatbot

    events = [
        {
            "content": {
                "parts": [
                    {
                        "functionResponse": {
                            "name": "chat_with_tutor",
                            "response": {
                                "message": "hi",
                                "profile": {"role": "sales", "experience_level": "beginner"},
                                "progress": {"xp": 10, "level": 1, "badges": []},
                            },
                        }
                    }
                ]
            }
        },
    ]
    result = chatbot._adk_extract_tool_result(events, "chat_with_tutor")
    assert result["profile"]["role"] == "sales"
    assert result["progress"]["xp"] == 10
    assert chatbot._adk_extract_tool_result(events, "some_other_tool") is None


def test_ask_prefers_the_adk_tutor_when_it_answers(monkeypatch):
    from web import chat as chatbot

    monkeypatch.setattr(
        chatbot,
        "ask_adk",
        lambda message, learner_id: {
            "reply": "an ADK-tutor reply",
            "profile": {"role": "sales"},
            "progress": {"xp": 5},
        },
    )
    result = chatbot.ask("what is a missing value?", "", session_id="s1")
    assert result["reply"] == "an ADK-tutor reply"
    assert result["grounded"] is True
    assert result["profile"] == {"role": "sales"}
    assert result["progress"] == {"xp": 5}


def test_ask_falls_back_when_adk_and_direct_llm_are_both_unavailable():
    from web import chat as chatbot

    # No ADK server at this test's pinned unreachable ADK_BASE_URL, and no
    # GEMINI_API_KEY in the test environment - both tiers should decline
    # honestly rather than raise.
    result = chatbot.ask("what is a missing value?", "", session_id="s1")
    assert result["grounded"] is False
    assert result["profile"] is None
    assert len(result["reply"]) > 0


def test_chat_uses_the_browsers_persistent_learner_id_when_given(monkeypatch):
    """The ADK tutor's memory should be keyed by the browser's own stable id,
    not this backend's much shorter-lived in-memory session id - otherwise
    the tutor never actually remembers anyone across visits."""
    from web import api as web_api

    h = _session()
    _load_sample(h)

    seen = {}

    def fake_ask(message, context, session_id=None, level=None):
        seen["session_id"] = session_id
        return {"reply": "ok", "grounded": True, "profile": None, "progress": None}

    monkeypatch.setattr(web_api.chatbot, "ask", fake_ask)

    client.post("/api/chat", headers=h, json={"message": "hi", "level_id": 0, "learner_id": "device-abc_123"})
    assert seen["session_id"] == "device-abc_123"

    # unsafe characters are stripped, not passed straight into a URL path
    client.post("/api/chat", headers=h, json={"message": "hi", "level_id": 0, "learner_id": "../weird/../id"})
    assert seen["session_id"] == "weirdid"

    # no learner_id at all falls back to this backend session's own id
    client.post("/api/chat", headers=h, json={"message": "hi", "level_id": 0})
    assert seen["session_id"] == list(h.values())[0]


def test_chat_folds_the_adk_profile_back_into_the_session(monkeypatch):
    """The whole point of pulling structured profile/progress out of the ADK
    reply: it should reshape this learner's session, not just sit inside one
    chat bubble."""
    from web import api as web_api

    h = _session(role=None, experience=None)  # starts with no profile, so ADK's should fill it in
    _load_sample(h)

    monkeypatch.setattr(
        web_api.chatbot,
        "ask",
        lambda message, context, session_id=None, level=None: {
            "reply": "got it",
            "grounded": True,
            "profile": {"role": "marketing", "experience_level": "intermediate", "learning_goal": "build_a_model"},
            "progress": {"xp": 40, "level": 2, "badges": ["first_lesson"]},
        },
    )

    r = client.post("/api/chat", headers=h, json={"message": "hello", "level_id": 0})
    body = r.json()
    assert body["grounded"] is True
    assert body["progress"] == {"xp": 40, "level": 2, "badges": ["first_lesson"]}

    state = client.get("/api/session/state", headers=h).json()
    assert state["profile"]["role"] == "marketing"
    assert state["profile"]["experience"] == "intermediate"


def test_level_callouts_are_grounded_in_the_real_level():
    h = _session()
    _load_sample(h)
    r = client.get("/api/levels/0/callouts", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["grounded"] is False
    assert len(body["callouts"]) == 3
    assert "deal_value" in body["callouts"][0]


def test_read_bonus_is_once_per_level():
    h = _session()
    _load_sample(h)
    first = client.post("/api/levels/0/read", headers=h).json()
    second = client.post("/api/levels/0/read", headers=h).json()
    assert first["awarded"] is True
    assert first["points_total"] == pipeline.READ_BONUS_POINTS
    assert second["awarded"] is False
    assert second["points_total"] == pipeline.READ_BONUS_POINTS  # not double-counted


def test_points_never_go_negative():
    h = _session()
    _load_sample(h)
    for i in range(4):
        r = client.post(f"/api/levels/{i}/guess", headers=h, json={"choice_id": "fail"}).json()
        assert r["points_total"] >= 0


def test_plain_keeps_numbers_drops_dashes():
    src = "skew shifted 21.3% (2.186 -> 2.651), exceeds 15.0% threshold -- distribution distorted"
    out = pipeline.plain(src)
    assert "21.3%" in out and "2.186 to 2.651" in out
    assert "--" not in out and "->" not in out and "—" not in out


def test_custom_csv_without_dates_still_works():
    csv = "group,amount\n" + "\n".join(
        f"{'A' if i % 2 else 'B'},{i * 3 if i % 7 else ''}" for i in range(60)
    )
    h = _session()
    r = client.post("/api/dataset", headers=h, files={"file": ("mini.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    assert client.get("/api/verify", headers=h).status_code == 200


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS: {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {fn.__name__} -- {e}")
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: {fn.__name__} -- {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)
