"""Job de teste: confirma que a conexão com o Postgres e o registro de execuções funcionam."""

from ocean.ingestion.jobs.base import JobResult
from ocean.shared.config import Settings
from ocean.storage.postgres.db import connect


def run(settings: Settings) -> JobResult:
    with connect(settings.database_url) as conn:
        conn.execute("SELECT 1")
    return JobResult(rows=1, source_version="ping")
