"""Teste de integração com Postgres real. Só roda se TEST_DATABASE_URL apontar para um banco
cujo nome contenha 'test' (o esquema public é APAGADO e recriado)."""

import os
from datetime import UTC, datetime
from urllib.parse import urlparse

import psycopg
import pytest

from ocean.ingestion.jobs import tides_yearly
from ocean.shared.config import REPO_ROOT, Settings
from ocean.storage.postgres.db import connect
from ocean.storage.postgres.migrate import apply_migrations

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL or "test" not in urlparse(URL).path, reason="TEST_DATABASE_URL não definido"
)

STATIONS = (
    "id,name,uf,latitude,longitude,chart_number,timezone,datum_note\n"
    "natal-rn,Porto de Natal,RN,-5.78,-35.21,,America/Fortaleza,\n"
    "recife-pe,Porto do Recife,PE,-8.0567,-34.8667,902,Etc/GMT+3,\n"
)

EVENTS = (
    "station_id,local_datetime,kind,height_m,edition\n"
    "natal-rn,2026-01-01 03:12,low,0.35,63\n"
    "natal-rn,2026-01-01 09:31,high,2.41,63\n"
)


@pytest.fixture
def conn():
    with connect(URL) as c:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
        c.commit()
        apply_migrations(c, REPO_ROOT / "migrations")
        c.commit()
        yield c


def _settings(tmp_path) -> Settings:
    data = tmp_path / "data"
    (data / "tides").mkdir(parents=True)
    (data / "tide_stations.csv").write_text(STATIONS, encoding="utf-8")
    (data / "tides" / "natal.csv").write_text(EVENTS, encoding="utf-8")
    return Settings(_env_file=None, database_url=URL, data_dir=data)


def test_job_loads_and_is_idempotent(conn, tmp_path):
    settings = _settings(tmp_path)
    first = tides_yearly.run(settings)
    second = tides_yearly.run(settings)
    assert first.rows == second.rows == 2 + 2 and first.source_version == "edições 63"
    assert conn.execute("SELECT count(*) AS n FROM tide_events").fetchone()["n"] == 2
    assert conn.execute("SELECT count(*) AS n FROM tide_stations").fetchone()["n"] == 2
    row = conn.execute(
        "SELECT event_at, kind, height_m FROM tide_events WHERE kind = 'low'"
    ).fetchone()
    assert row["event_at"] == datetime(2026, 1, 1, 6, 12, tzinfo=UTC)  # o mesmo instante, em UTC
    assert float(row["height_m"]) == 0.35


def test_reload_updates_height(conn, tmp_path):
    settings = _settings(tmp_path)
    tides_yearly.run(settings)
    path = settings.data_dir / "tides" / "natal.csv"
    path.write_text(EVENTS.replace("0.35", "0.40"), encoding="utf-8")
    tides_yearly.run(settings)
    heights = [
        float(r["height_m"])
        for r in conn.execute("SELECT height_m FROM tide_events WHERE kind='low'")
    ]
    assert heights == [0.40]


def test_unknown_station_fails_before_touching_db(conn, tmp_path):
    settings = _settings(tmp_path)
    (settings.data_dir / "tides" / "natal.csv").write_text(
        EVENTS.replace("natal-rn", "xx"), encoding="utf-8"
    )
    with pytest.raises(ValueError):
        tides_yearly.run(settings)
    assert conn.execute("SELECT count(*) AS n FROM tide_stations").fetchone()["n"] == 0


def test_psycopg_is_available():
    assert psycopg.__version__
