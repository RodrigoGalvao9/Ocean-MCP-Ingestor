"""Escrita de estações e eventos de maré (usada só pela ingestão, com usuário admin)."""

import psycopg

from ocean.domain.models.tide import TideEvent, TideStation

_STATION_SQL = """
INSERT INTO tide_stations (id, name, uf, latitude, longitude, chart_number, timezone, datum_note)
VALUES (%(id)s, %(name)s, %(uf)s, %(latitude)s, %(longitude)s, %(chart_number)s,
        %(timezone)s, %(datum_note)s)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name, uf = EXCLUDED.uf, latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude, chart_number = EXCLUDED.chart_number,
    timezone = EXCLUDED.timezone, datum_note = EXCLUDED.datum_note
"""

_EVENT_SQL = """
INSERT INTO tide_events (station_id, event_at, kind, height_m, edition)
VALUES (%(station_id)s, %(at)s, %(kind)s, %(height_m)s, %(edition)s)
ON CONFLICT (station_id, event_at, kind) DO UPDATE SET
    height_m = EXCLUDED.height_m, edition = EXCLUDED.edition
"""


def upsert_stations(conn: psycopg.Connection, stations: list[TideStation]) -> int:
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(_STATION_SQL, [s.model_dump() for s in stations])
    return len(stations)


def upsert_events(conn: psycopg.Connection, events: list[TideEvent]) -> int:
    """Idempotente: repetir a carga atualiza as mesmas linhas em vez de duplicar."""
    with conn.transaction(), conn.cursor() as cur:
        cur.executemany(_EVENT_SQL, [e.model_dump() for e in events])
    return len(events)
