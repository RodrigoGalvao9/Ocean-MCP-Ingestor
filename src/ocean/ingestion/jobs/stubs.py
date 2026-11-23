"""Jobs planejados e ainda não implementados. Cada um indica a fase do plano."""

from collections.abc import Callable

from ocean.ingestion.jobs.base import JobResult
from ocean.shared.config import Settings


def _not_implemented(name: str, phase: str) -> Callable[[Settings], JobResult]:
    def run(settings: Settings) -> JobResult:
        raise NotImplementedError(f"job '{name}' ainda não implementado (planejado: {phase})")

    return run


mpa_registry = _not_implemented("mpa_registry", "fase 4")
markets_load = _not_implemented("markets_load", "fase 5")
