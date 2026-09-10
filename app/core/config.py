"""
Single place that reads the environment. Nothing else in the codebase calls
os.environ for configuration, so switching provider or storage location is a
one-file change and there is never a hardcoded key anywhere.
"""

from __future__ import annotations

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env if python-dotenv is available. Optional on purpose -- the platform
# must run with no .env at all (deterministic fallback mode).
try:  # pragma: no cover - trivial
    from dotenv import load_dotenv
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:  # pragma: no cover - trivial
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


class Settings:
    """
    Resolved at import time but re-readable via refresh() so tests can flip
    provider without reloading modules.
    """

    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.project_root = PROJECT_ROOT
        self.llm_provider = _env("LLM_PROVIDER", "auto").lower() or "auto"
        self.gemini_api_key = _env("GEMINI_API_KEY")
        self.gemini_model = _env("GEMINI_MODEL", "gemini-3.6-flash")
        self.anthropic_api_key = _env("ANTHROPIC_API_KEY")
        self.anthropic_model = _env("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        self.llm_max_retries = int(_env("LLM_MAX_RETRIES", "2"))
        self.state_dir = _env("STATE_DIR", os.path.join(PROJECT_ROOT, "data", "state"))
        self.upload_dir = _env("UPLOAD_DIR", os.path.join(PROJECT_ROOT, "data", "uploads"))
        self.chart_dir = _env("CHART_DIR", os.path.join(PROJECT_ROOT, "data", "charts"))
        self.demo_dataset = os.path.join(PROJECT_ROOT, "data", "messy_sales_dataset.csv")

    def resolved_provider(self) -> str:
        """
        Which provider will actually be used. "mock" means no key is set and
        the whole platform runs on deterministic text -- the supported,
        documented default, not a degraded state.
        """
        if self.llm_provider == "mock":
            return "mock"
        if self.llm_provider == "gemini":
            return "gemini" if self.gemini_api_key else "mock"
        if self.llm_provider == "anthropic":
            return "anthropic" if self.anthropic_api_key else "mock"
        # auto
        if self.gemini_api_key:
            return "gemini"
        if self.anthropic_api_key:
            return "anthropic"
        return "mock"

    def llm_enabled(self) -> bool:
        return self.resolved_provider() != "mock"

    def ensure_dirs(self) -> None:
        for d in (self.state_dir, self.upload_dir, self.chart_dir):
            os.makedirs(d, exist_ok=True)


settings = Settings()
