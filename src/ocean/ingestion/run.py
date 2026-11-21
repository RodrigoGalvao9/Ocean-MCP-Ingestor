"""Executa um job de ingestão e registra a execução em ingestion_runs.

    python -m ocean.ingestion.run ping
    python -m ocean.ingestion.run knowledge_refresh
"""

import argparse
import logging
import sys

from ocean.ingestion.jobs import REGISTRY
from ocean.shared.config import get_settings
from ocean.shared.logging import configure_logging
from ocean.storage.postgres import runs
from ocean.storage.postgres.db import connect

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Executa um job de ingestão do Ocean.")
    parser.add_argument("job", choices=sorted(REGISTRY))
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)

    conn = connect() if settings.database_url else None
    if conn is None:
        log.warning("DATABASE_URL ausente: a execução não será registrada em ingestion_runs")
    run_id = runs.start_run(conn, args.job) if conn else None

    try:
        result = REGISTRY[args.job](settings)
    except Exception as exc:
        log.exception("job falhou", extra={"job": args.job})
        if conn and run_id:
            runs.finish_run(conn, run_id, "failed", error=f"{type(exc).__name__}: {exc}")
        return 1
    else:
        if conn and run_id:
            runs.finish_run(conn, run_id, "ok", result.rows, source_version=result.source_version)
        log.info("job concluído", extra={"job": args.job, "rows": result.rows})
        return 0
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
