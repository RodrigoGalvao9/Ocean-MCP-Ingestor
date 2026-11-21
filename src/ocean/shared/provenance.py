"""Contrato de resposta de TODA ferramenta MCP.

O agente usa estes campos para citar a fonte, dizer a que momento o dado se refere e
admitir lacunas. Datas sempre em UTC; quando a fonte usa horário legal (marés),
isso vai em `metadata`.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(UTC)


class Status(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class Freshness(StrEnum):
    LIVE = "live"
    RECENT = "recent"
    HISTORICAL = "historical"
    REFERENCE = "reference"  # conteúdo de referência, sem data (glossário, explicações)


class MaritimeDataResponse(BaseModel):
    status: Status
    source: str
    source_url: str | None = None
    attribution: str | None = None
    license: str | None = None
    retrieved_at: datetime = Field(default_factory=utcnow)  # quando consultamos
    data_timestamp: datetime | None = None  # a que momento o dado se refere
    freshness: Freshness
    data: dict[str, Any] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def unavailable(cls, source: str, reason: str, **kwargs: Any) -> "MaritimeDataResponse":
        kwargs.setdefault("freshness", Freshness.LIVE)
        return cls(
            status=Status.UNAVAILABLE,
            source=source,
            limitations=[reason],
            **kwargs,
        )

    def to_tool_result(self) -> dict[str, Any]:
        """Formato devolvido pelas ferramentas MCP (JSON puro)."""
        return self.model_dump(mode="json")
