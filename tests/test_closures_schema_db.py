"""Esquema do defeso em Postgres real (mesmas regras de TEST_DATABASE_URL das outras suítes)."""

import os
from urllib.parse import urlparse

import psycopg
import pytest

from ocean.shared.config import REPO_ROOT
from ocean.storage.postgres.db import connect
from ocean.storage.postgres.migrate import apply_migrations

URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not URL or "test" not in urlparse(URL).path, reason="TEST_DATABASE_URL não definido"
)

INSERT = (
    "INSERT INTO fishing_closures (species, environment, prohibition_start, prohibition_end,"
    " year, legal_reference) VALUES (%s, 'marine', %s, %s, %s, 'Portaria X') RETURNING id"
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


def test_insert_area_and_cascade(conn):
    cid = conn.execute(INSERT, ("Lagosta", "11-01", "04-30", None)).fetchone()["id"]
    conn.execute(
        "INSERT INTO fishing_closure_areas (closure_id, uf, ibge_code, municipality)"
        " VALUES (%s, 'PE', '2611606', 'Recife'), (%s, 'PE', '', NULL)",
        (cid, cid),
    )
    assert conn.execute("SELECT count(*) AS n FROM fishing_closure_areas").fetchone()["n"] == 2
    conn.execute("DELETE FROM fishing_closures WHERE id = %s", (cid,))
    assert conn.execute("SELECT count(*) AS n FROM fishing_closure_areas").fetchone()["n"] == 0


@pytest.mark.parametrize("start", ["13-01", "00-10", "1-1", "01-32", "2026-01-01"])
def test_rejects_invalid_month_day(conn, start):
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(INSERT, ("Lagosta", start, "04-30", None))


def test_unique_key_treats_null_year_as_one_value(conn):
    conn.execute(INSERT, ("Lagosta", "11-01", "04-30", None))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(INSERT, ("Lagosta", "11-01", "04-30", None))
    conn.rollback()
    conn.execute(INSERT, ("Caranguejo", "01-18", "01-23", 2026))
    conn.execute(INSERT, ("Caranguejo", "01-18", "01-23", 2027))  # outro ano: permitido
