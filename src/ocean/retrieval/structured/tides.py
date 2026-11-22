"""Consultas de marés no Postgres (somente leitura)."""

from datetime import datetime

import psycopg

from ocean.domain.models.tide import TideEvent, TideStation


def stations_with_events(
    conn: psycopg.Connection, start: datetime, end: datetime
) -> list[TideStation]:
    """Estações que têm eventos em [start, end]; só elas podem responder à consulta."""
    rows = conn.execute(
        """
        SELECT s.id, s.name, s.uf, s.latitude, s.longitude, s.chart_number, s.timezone, s.datum_note
        FROM tide_stations s
        WHERE EXISTS (
            SELECT 1 FROM tide_events e
            WHERE e.station_id = s.id AND e.event_at BETWEEN %s AND %s
        )
        """,
        (start, end),
    ).fetchall()
    return [TideStation(**row) for row in rows]


def events_between(
    conn: psycopg.Connection, station_id: str, start: datetime, end: datetime
) -> list[TideEvent]:
    rows = conn.execute(
        """
        SELECT station_id, event_at AS at, kind, height_m::float AS height_m, edition
        FROM tide_events
        WHERE station_id = %s AND event_at BETWEEN %s AND %s
        ORDER BY event_at
        """,
        (station_id, start, end),
    ).fetchall()
    return [TideEvent(**row) for row in rows]
