"""Interpretação de eventos de maré (preamar e baixa-mar)."""

from dataclasses import dataclass
from datetime import datetime, timedelta
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


MIN_SWING_M = 0.10
MAX_RIPPLE_SPAN = timedelta(hours=8)  # dois extremos iguais mais distantes que isso = lacuna


def significant_extremes(
    events: list[TideEvent], min_swing_m: float = MIN_SWING_M
) -> list[TideEvent]:
    """Remove ondulações: a tábua da DHN lista todo extremo local, inclusive oscilações de
    poucos centímetros (Santos, Itaguaí, Angra). Mantém só os extremos que se afastam do
    anterior em pelo menos `min_swing_m`; entre dois do mesmo tipo fica o mais extremo.
    O limite de 0,10 m é uma escolha do Ocean, não da DHN."""
    ordered = sorted(events, key=lambda e: e.at)
    if len(ordered) < 2:
        return ordered
    kept: list[TideEvent] = []
    candidate = ordered[0]
    for event in ordered[1:]:
        if event.kind == candidate.kind and event.at - candidate.at > MAX_RIPPLE_SPAN:
            # Mesmo tipo e longe no tempo não é ondulação: falta o evento do meio na tábua.
            # Mantém os dois para que a fase fique "indeterminada" em vez de errada.
            kept.append(candidate)
            candidate = event
        elif event.kind == candidate.kind:
            more_extreme = (
                event.height_m > candidate.height_m
                if event.kind == "high"
                else event.height_m < candidate.height_m
            )
            if more_extreme:
                candidate = event
        elif abs(event.height_m - candidate.height_m) >= min_swing_m:
            kept.append(candidate)
            candidate = event
    kept.append(candidate)
    return kept
