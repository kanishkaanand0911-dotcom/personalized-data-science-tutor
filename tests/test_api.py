"""
Tests for the FastAPI layer.

Skipped cleanly if FastAPI isn't installed -- it's an optional dependency and
the rest of the platform must still be testable without it.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Each test gets its own state, upload and chart directories, so API
    tests never inherit another test's XP or uploaded file."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "state_dir", str(tmp_path / "state"))
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "chart_dir", str(tmp_path / "charts"))
    settings.ensure_dirs()

    import app.main as main
    from app.agents.orchestrator import Orchestrator
    from app.core.state import StateStore

    store = StateStore(str(tmp_path / "state"))
    monkeypatch.setattr(main, "store", store)
    monkeypatch.setattr(main, "orchestrator", Orchestrator(store=store))
    monkeypatch.setattr(main, "_frames", {})
    return TestClient(main.app)


def test_root_lists_agents_and_llm_mode(client):
    body = client.get("/").json()
    assert len(body["agents"]) == 9
    assert body["llm"]["mode"] in ("llm", "deterministic-fallback")


def test_onboard_creates_profile_and_path(client):
    body = client.post("/onboard", json={
        "user_id": "u1",
        "message": "I work in sales, I'm a complete beginner and I want to learn visualization with my sales data",
    }).json()
    assert body["profile"]["role"] == "sales"
    assert client.get("/learning-path?user_id=u1").status_code == 200


def test_learning_path_404s_before_onboarding(client):
    assert client.get("/learning-path?user_id=nobody").status_code == 404


def test_upload_analyze_lesson_quiz_challenge_flow(client):
    client.post("/onboard", json={"user_id": "u2",
                                   "message": "I work in sales, beginner, I want to visualize my data"})

    with open("data/messy_sales_dataset.csv", "rb") as fh:
        upload = client.post("/upload-data?user_id=u2&target_col=deal_value",
                             files={"file": ("messy.csv", fh, "text/csv")})
    assert upload.status_code == 200
    assert "data_agent" in upload.json()["agents_called"]

    lesson = client.get("/lesson/current?user_id=u2").json()
    assert "teacher_agent" in lesson["agents_called"]

    quiz = next(r["data"]["quiz"] for r in lesson["responses"] if r["agent"] == "quiz_agent")
    answered = client.post("/quiz/answer", json={"user_id": "u2", "quiz": quiz,
                                                  "answer_index": quiz["correct_index"]})
    assert answered.status_code == 200

    challenge = next(r["data"]["challenge"] for r in lesson["responses"] if r["agent"] == "practice_agent")
    submitted = client.post("/challenge/submit", json={
        "user_id": "u2", "challenge": challenge,
        "answer": "Each row is one record and the file has 350 rows and 8 columns",
    })
    assert submitted.status_code == 200

    progress = client.get("/progress?user_id=u2").json()
    assert progress["xp"] > 0
    assert progress["lessons_completed"] == 1


def test_upload_rejects_a_non_csv(client):
    response = client.post("/upload-data?user_id=u3",
                           files={"file": ("notes.txt", b"hello", "text/plain")})
    assert response.status_code == 400


def test_analyze_data_404s_without_an_upload(client):
    assert client.post("/analyze-data", json={"user_id": "nobody"}).status_code == 404


def test_chart_endpoint_refuses_paths_outside_the_chart_directory(client):
    """Without the containment check this endpoint would serve any file the
    process can read."""
    assert client.get("/chart?path=/etc/passwd").status_code == 404


def test_chat_routes_to_the_right_agent(client):
    client.post("/onboard", json={"user_id": "u4", "message": "I work in sales and I'm a beginner"})
    assert client.post("/chat", json={"user_id": "u4", "message": "how am I doing"}).json()["intent"] == "progress"
