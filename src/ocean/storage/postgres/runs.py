"""Registro das execuções de ingestão (tabela ingestion_runs)."""

import psycopg


def start_run(conn: psycopg.Connection, job: str) -> int:
    row = conn.execute(
        "INSERT INTO ingestion_runs (job, status) VALUES (%s, 'running') RETURNING id", (job,)
    ).fetchone()
    conn.commit()
    return row["id"]


def finish_run(
    conn: psycopg.Connection,
    run_id: int,
    status: str,
    rows_affected: int = 0,
    error: str | None = None,
    source_version: str | None = None,
) -> None:
    conn.execute(
        "UPDATE ingestion_runs SET finished_at = now(), status = %s, rows_affected = %s, "
        "error = %s, source_version = %s WHERE id = %s",
        (status, rows_affected, error, source_version, run_id),
    )
    conn.commit()
