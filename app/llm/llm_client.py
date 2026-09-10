"""
Concrete providers + the factory the rest of the system uses.

Only get_llm_client() should be imported elsewhere. It reads app.core.config
once and hands back a singleton, so agents never see a provider name, never
see an API key, and never need changing when the provider does.

Both real providers are lazy: the SDK is imported inside the constructor, so
the platform runs fine in an environment where neither SDK is installed.
"""

from __future__ import annotations

import time

from app.core.config import settings
from app.llm.base_client import BaseLLMClient, MockClient


class GeminiClient(BaseLLMClient):
    """Google Gemini backend -- the original project's provider, preserved."""

    name = "gemini"

    def __init__(self, api_key: str, model: str, max_retries: int = 2) -> None:
        super().__init__()
        from google import genai  # imported lazily so the SDK is optional
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_retries = max_retries

    def _generate(self, system: str, user: str, max_tokens: int) -> str | None:
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config={
                        "system_instruction": system,
                        # Newer Gemini models spend part of the budget before
                        # the visible answer, so a low ceiling truncates the
                        # response. 900 is the floor the original llm_client
                        # settled on after seeing real truncation.
                        "max_output_tokens": max(max_tokens, 900),
                    },
                )
                text = (response.text or "").strip()
                if not text:
                    raise ValueError("empty response text")
                return text
            except Exception as e:  # noqa: BLE001 -- any failure routes to the fallback
                last_error = e
                if attempt < self._max_retries:
                    time.sleep(0.5 * (2 ** attempt))
        print(f"[llm:gemini] all {self._max_retries + 1} attempts failed: {last_error}")
        return None


class AnthropicClient(BaseLLMClient):
    """Anthropic backend -- the provider app/educator_anthropic_backup was written against."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str, max_retries: int = 2) -> None:
        super().__init__()
        import anthropic  # imported lazily so the SDK is optional
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_retries = max_retries

    def _generate(self, system: str, user: str, max_tokens: int) -> str | None:
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=max(max_tokens, 512),
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(
                    block.text for block in response.content if getattr(block, "type", "") == "text"
                ).strip()
                if not text:
                    raise ValueError("empty response text")
                return text
            except Exception as e:  # noqa: BLE001
                last_error = e
                if attempt < self._max_retries:
                    time.sleep(0.5 * (2 ** attempt))
        print(f"[llm:anthropic] all {self._max_retries + 1} attempts failed: {last_error}")
        return None


_client: BaseLLMClient | None = None


def get_llm_client(force_refresh: bool = False) -> BaseLLMClient:
    """
    The single entry point. Falls back to MockClient if the configured
    provider's SDK isn't installed or its constructor fails -- a missing
    optional dependency must never take the platform down.
    """
    global _client
    if _client is not None and not force_refresh:
        return _client

    if force_refresh:
        settings.refresh()

    provider = settings.resolved_provider()
    try:
        if provider == "gemini":
            _client = GeminiClient(settings.gemini_api_key, settings.gemini_model, settings.llm_max_retries)
        elif provider == "anthropic":
            _client = AnthropicClient(settings.anthropic_api_key, settings.anthropic_model, settings.llm_max_retries)
        else:
            _client = MockClient()
    except Exception as e:  # noqa: BLE001
        print(f"[llm] could not initialise provider '{provider}' ({e}); using deterministic mode")
        _client = MockClient()

    return _client


def llm_status() -> dict:
    client = get_llm_client()
    return {
        "provider": client.name,
        "enabled": client.enabled,
        "mode": "llm" if client.enabled else "deterministic-fallback",
    }
