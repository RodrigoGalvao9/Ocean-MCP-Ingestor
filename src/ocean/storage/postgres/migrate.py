"""Aplica os arquivos de migrations/*.sql, em ordem, uma única vez cada.

    python -m ocean.storage.postgres.migrate

A ingestão é a dona do esquema: só ela deve rodar isto (usuário admin).
"""

import logging
from pathlib import Path

import psycopg

from ocean.shared.config import get_settings
from ocean.shared.logging import configure_logging
from ocean.storage.postgres.db import connect

log = logging.getLogger(__name__)


def apply_migrations(conn: psycopg.Connection, migrations_dir: Path) -> list[str]:
    with conn.transaction():
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
        )
    applied = {r["filename"] for r in conn.execute("SELECT filename FROM schema_migrations")}

    newly_applied: list[str] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in applied:
            continue
        with conn.transaction():
            conn.execute(path.read_text(encoding="utf-8"))
            conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
        log.info("migration aplicada", extra={"file": path.name})
        newly_applied.append(path.name)
    return newly_applied


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    with connect() as conn:
        done = apply_migrations(conn, settings.migrations_dir)
    log.info("migrations concluídas", extra={"applied": done})


if __name__ == "__main__":
    main()
