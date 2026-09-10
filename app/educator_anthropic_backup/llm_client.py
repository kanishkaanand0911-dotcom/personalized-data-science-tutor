"""
Low-level LLM call wrapper. Same as before: cheap/fast model, retry with
backoff, in-memory cache. narrate_llm.py never touches the API directly —
this is the only file that would change if you swap providers.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

import anthropic

MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_SECONDS = 8.0
MAX_RETRIES = 2

_client: anthropic.Anthropic | None = None
_cache: dict[str, str] = {}


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY"),
            timeout=TIMEOUT_SECONDS,
        )
    return _client


def _cache_key(system: str, user: str) -> str:
    payload = json.dumps({"system": system, "user": user}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def call_llm(system: str, user: str, max_tokens: int = 100) -> str | None:
    """Returns the model's text response, or None if every attempt failed —
    or if no API key is set at all, which is the expected state until B
    plugs in real credentials."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    key = _cache_key(system, user)
    if key in _cache:
        return _cache[key]

    client = _get_client()
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = response.content[0].text.strip()
            _cache[key] = text
            return text
        except Exception as e:  # noqa: BLE001 — any failure -> fallback, never crash the demo
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(0.5 * (2 ** attempt))

    print(f"[llm_client] all {MAX_RETRIES + 1} attempts failed: {last_error}")
    return None
