"""Registro dos jobs de ingestão. Para criar um job: novo módulo com `run(settings)` e uma
linha em REGISTRY (e na lista de opções de .github/workflows/ingest.yml)."""

from collections.abc import Callable

from ocean.ingestion.jobs import knowledge_refresh, ping, stubs, tides_yearly
from ocean.ingestion.jobs.base import JobResult
from ocean.shared.config import Settings

REGISTRY: dict[str, Callable[[Settings], JobResult]] = {
    "ping": ping.run,
    "knowledge_refresh": knowledge_refresh.run,
    "tides_yearly": tides_yearly.run,
    "mpa_closures": stubs.mpa_closures,
    "mpa_registry": stubs.mpa_registry,
    "markets_load": stubs.markets_load,
}
