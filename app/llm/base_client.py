"""
The provider-agnostic contract every LLM backend implements.

The whole multi-agent system depends only on this interface, so swapping
Gemini for Anthropic (or for the offline MockClient) touches exactly one
file -- app/llm/llm_client.py -- and no agent code at all.
"""

from __future__ import annotations

import abc
import hashlib
import json


class BaseLLMClient(abc.ABC):
    """
    complete() returns the model's text, or None on any failure.

    Returning None rather than raising is deliberate: every caller in this
    codebase already has a deterministic fallback, so a None simply means
    "use the fallback" and the platform never breaks because of an API
    hiccup, a missing key, or a rate limit.
    """

    name: str = "base"

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}

    @abc.abstractmethod
    def _generate(self, system: str, user: str, max_tokens: int) -> str | None:
        ...

    @staticmethod
    def _cache_key(system: str, user: str, max_tokens: int) -> str:
        payload = json.dumps({"s": system, "u": user, "m": max_tokens}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def complete(self, system: str, user: str, max_tokens: int = 400) -> str | None:
        key = self._cache_key(system, user, max_tokens)
        if key in self._cache:
            return self._cache[key]
        text = self._generate(system, user, max_tokens)
        if text:
            self._cache[key] = text
        return text

    def complete_json(self, system: str, user: str, max_tokens: int = 600) -> dict | list | None:
        """
        For agents that need structured output. Strips markdown fences that
        models add despite being told not to, and returns None (never a
        partially-parsed object) if the result isn't valid JSON -- the caller
        then uses its deterministic version instead.
        """
        raw = self.complete(system, user, max_tokens)
        if not raw:
            return None
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1] if "```" in cleaned[3:] else cleaned[3:]
            if cleaned.lstrip().startswith("json"):
                cleaned = cleaned.lstrip()[4:]
        cleaned = cleaned.strip().strip("`").strip()
        try:
            return json.loads(cleaned)
        except (ValueError, TypeError):
            return None

    @property
    def enabled(self) -> bool:
        return True


class MockClient(BaseLLMClient):
    """
    The no-API-key backend. It does not fake LLM output -- it returns None
    for everything, which routes every agent to its deterministic path.
    That is what makes `python demo_personalized.py` work with no key and
    still produce real, grounded teaching content.
    """

    name = "mock"

    def _generate(self, system: str, user: str, max_tokens: int) -> str | None:
        return None

    @property
    def enabled(self) -> bool:
        return False
