"""
Offline tests, no real API key needed. GEMINI VERSION -- mocks match
google-genai's response shape (response.text) instead of Anthropic's
(response.content[0].text). Run: python3 test_harness.py
"""

from unittest.mock import MagicMock, patch

import llm_client
from narrate_llm import narrate_llm, explain_action, generate_lesson
from fake_data import FAKE_ACTION_LOG, FAKE_MODEL_LOG


def _make_mock_client(response_text=None, raise_error=False):
    mock_client = MagicMock()
    if raise_error:
        mock_client.models.generate_content.side_effect = RuntimeError("simulated API failure")
    else:
        mock_response = MagicMock()
        mock_response.text = response_text
        mock_client.models.generate_content.return_value = mock_response
    return mock_client


def test_no_key_falls_back_silently_without_retry_delay():
    llm_client._cache.clear()
    with patch.dict("os.environ", {}, clear=True):
        result = narrate_llm(FAKE_ACTION_LOG[0])
        assert result == explain_action(FAKE_ACTION_LOG[0])
    print("PASS: no API key -> immediate, silent fallback to the deterministic explanation")


def test_falls_back_on_total_api_failure():
    llm_client._cache.clear()
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key-for-test"}):
        with patch.object(llm_client, "_get_client", return_value=_make_mock_client(raise_error=True)):
            result = narrate_llm(FAKE_ACTION_LOG[0])
            assert result == explain_action(FAKE_ACTION_LOG[0])
    print("PASS: API configured but failing -> falls back after retries, doesn't crash")


def test_uses_llm_response_when_available():
    llm_client._cache.clear()
    canned = "The revenue column had some missing values, and the median fix made things worse, so it was undone."
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key-for-test"}):
        with patch.object(llm_client, "_get_client", return_value=_make_mock_client(response_text=canned)):
            result = narrate_llm(FAKE_ACTION_LOG[0])
            assert result == canned
    print("PASS: uses the LLM's rewording when the call succeeds")


def test_generate_lesson_same_shape_with_and_without_llm():
    llm_client._cache.clear()
    with patch.dict("os.environ", {}, clear=True):
        no_llm = generate_lesson(FAKE_ACTION_LOG, FAKE_MODEL_LOG)

    llm_client._cache.clear()
    with patch.dict("os.environ", {"GEMINI_API_KEY": "fake-key-for-test"}):
        with patch.object(llm_client, "_get_client", return_value=_make_mock_client(response_text="reworded")):
            with_llm = generate_lesson(FAKE_ACTION_LOG, FAKE_MODEL_LOG)

    assert no_llm.startswith("## What happened to your data")
    assert with_llm.startswith("## What happened to your data")
    assert "## Model selection" in no_llm and "## Model selection" in with_llm
    print("PASS: generate_lesson() returns the same structure whether or not the LLM is configured")


if __name__ == "__main__":
    test_no_key_falls_back_silently_without_retry_delay()
    test_falls_back_on_total_api_failure()
    test_uses_llm_response_when_available()
    test_generate_lesson_same_shape_with_and_without_llm()
    print("\nAll offline logic tests passed.")
