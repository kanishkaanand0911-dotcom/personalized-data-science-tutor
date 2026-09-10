"""
The contract every agent obeys.

Three rules make this a genuine multi-agent system rather than one prompt
wearing several hats:

  1. Each agent has ONE responsibility and cannot do another agent's job --
     the teacher never analyses data, the data agent never writes a lesson.
  2. Each agent declares a typed input and returns an AgentResponse, so the
     orchestrator routes on structure, not on parsing prose.
  3. Every agent works with no LLM at all. `used_llm` on the response records
     which path actually ran, so a demo without an API key is honest about it
     rather than silently degraded.
"""

from __future__ import annotations

import abc

from app.core.schemas import AgentResponse
from app.llm.llm_client import get_llm_client


class Agent(abc.ABC):
    name: str = "agent"
    responsibility: str = ""

    def __init__(self) -> None:
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            self._llm = get_llm_client()
        return self._llm

    @property
    def llm_enabled(self) -> bool:
        return self.llm.enabled

    @abc.abstractmethod
    def run(self, **kwargs) -> AgentResponse:
        """Do this agent's one job."""

    def _respond(self, intent: str, message: str, data: dict | None = None,
                 used_llm: bool = False) -> AgentResponse:
        return AgentResponse(agent=self.name, intent=intent, message=message,
                             data=data or {}, used_llm=used_llm)

    def describe(self) -> dict:
        return {"name": self.name, "responsibility": self.responsibility}
