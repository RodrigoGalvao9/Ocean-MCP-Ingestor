"""Interpretação de eventos de maré (preamar e baixa-mar)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from ocean.domain.models.tide import TideEvent

Phase = Literal["rising", "falling", "unknown"]
PHASE_LABEL_PT = {"rising": "enchente", "falling": "vazante", "unknown": "indeterminada"}


@dataclass(frozen=True)
class TideState:
    phase: Phase
    previous: TideEvent | None
    next_high: TideEvent | None
    next_low: TideEvent | None

    @property
    def phase_pt(self) -> str:
        return PHASE_LABEL_PT[self.phase]


def tide_state(now: datetime, events: list[TideEvent]) -> TideState:
    """Fase da maré em `now` (enchente se o próximo evento é preamar, vazante se é baixa-mar)."""
    ordered = sorted(events, key=lambda e: e.at)
    previous = next((e for e in reversed(ordered) if e.at <= now), None)
    upcoming = [e for e in ordered if e.at > now]
    following = upcoming[0] if upcoming else None

    phase: Phase = "unknown"
    # As marés alternam preamar e baixa-mar; evento anterior igual ao seguinte = dado faltando.
    if following and not (previous and previous.kind == following.kind):
        phase = "rising" if following.kind == "high" else "falling"

    return TideState(
        phase=phase,
        previous=previous,
        next_high=next((e for e in upcoming if e.kind == "high"), None),
        next_low=next((e for e in upcoming if e.kind == "low"), None),
    )
