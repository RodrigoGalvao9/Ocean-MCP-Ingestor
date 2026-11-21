"""Carrega estações (data/tide_stations.csv) e eventos de maré (data/tides/*.csv) no Postgres.

Idempotente. A origem dos CSVs pode ser um parser de PDF da DHN ou tábuas transcritas à mão.
"""

import logging

from ocean.ingestion.jobs.base import JobResult
from ocean.ingestion.parsers import tide_csv
from ocean.shared.config import Settings
from ocean.storage.postgres import tides
from ocean.storage.postgres.db import connect

log = logging.getLogger(__name__)


def run(settings: Settings) -> JobResult:
    stations_path = settings.data_dir / "tide_stations.csv"
    stations = tide_csv.load_stations(stations_path)
    by_id = {s.id: s for s in stations}

    events = []
    files = sorted((settings.data_dir / "tides").glob("*.csv"))
    for path in files:
        parsed = tide_csv.parse_events(path, by_id)
        log.info("arquivo de marés lido", extra={"file": path.name, "events": len(parsed)})
        events.extend(parsed)
    if not files:
        log.warning("nenhum CSV em data/tides: só as estações serão carregadas")
    for warning in tide_csv.check_alternation(events):
        log.warning("possível linha faltando: %s", warning)

    with connect(settings.database_url) as conn:
        total = tides.upsert_stations(conn, stations) + tides.upsert_events(conn, events)

    editions = sorted({e.edition for e in events if e.edition is not None})
    version = "edições " + ",".join(map(str, editions)) if editions else None
    return JobResult(rows=total, source_version=version)
