# ruff: noqa: E501
import os
from urllib.parse import urlparse

import pytest

from ocean.ingestion.parsers import defeso_csv as dc

C_HEADER = (
    "key,species,scientific_name,region,environment,prohibition_start,prohibition_end,year,"
    "fishing_type,legal_reference,source_url,source_type,last_verified_at,notes\n"
)
A_HEADER = "closure_key,uf,ibge_code,municipality\n"


def _write(tmp_path, closures, areas, prefix="x"):
    c, a = tmp_path / f"{prefix}_closures.csv", tmp_path / f"{prefix}_areas.csv"
    c.write_text(C_HEADER + closures, encoding="utf-8")
    a.write_text(A_HEADER + areas, encoding="utf-8")
    return c, a


LAGOSTA = (
    "k1,Lagosta,Panulirus argus,PE,marine,11-01,04-30,,,Portaria 221/2021,,official,2026-08-12,\n"
)


def test_load_pair_ok(tmp_path):
    c, a = _write(tmp_path, LAGOSTA, "k1,PE,2611606,Recife\nk1,RN,,\n")
    [item] = dc.load_pair(c, a)
    assert item.closure.year is None and item.closure.last_verified_at.isoformat() == "2026-08-12"
    assert item.areas == {("PE", "2611606"): "Recife", ("RN", ""): None}


@pytest.mark.parametrize(
    "closures,areas,message",
    [
        (LAGOSTA.replace("11-01", "13-01"), "k1,PE,,\n", "início inválido"),
        (LAGOSTA.replace("04-30", "02-30"), "k1,PE,,\n", "fim inválido"),
        (LAGOSTA.replace("marine", "ocean"), "k1,PE,,\n", "ambiente inválido"),
        (LAGOSTA, "k2,PE,,\n", "defeso desconhecido"),
        (LAGOSTA, "k1,pe,,\n", "área inválida"),
        (LAGOSTA, "k1,PE,123,\n", "área inválida"),
        (LAGOSTA, "", "sem área"),
        (LAGOSTA + LAGOSTA, "k1,PE,,\n", "chave repetida"),
    ],
)
def test_load_pair_rejects_bad_rows(tmp_path, closures, areas, message):
    c, a = _write(tmp_path, closures, areas)
    with pytest.raises(dc.DefesoCsvError, match=message):
        dc.load_pair(c, a)


def test_missing_columns(tmp_path):
    c = tmp_path / "c.csv"
    a = tmp_path / "a.csv"
    c.write_text("key,species\nk,x\n", encoding="utf-8")
    a.write_text(A_HEADER, encoding="utf-8")
    with pytest.raises(dc.DefesoCsvError, match="faltam colunas"):
        dc.load_pair(c, a)


def test_merge_unions_areas_and_last_group_wins(tmp_path):
    c1, a1 = _write(tmp_path, LAGOSTA, "k1,PE,2611606,Recife\n", "m")
    c2, a2 = _write(
        tmp_path, LAGOSTA.replace(",,official", ",artesanal,official"), "k1,RN,,\n", "k"
    )
    merged = dc.merge([dc.load_pair(c1, a1), dc.load_pair(c2, a2)])
    assert len(merged) == 1
    assert set(merged[0].areas) == {("PE", "2611606"), ("RN", "")}


# --- Postgres real -----------------------------------------------------------------------
URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(
    not URL or "test" not in urlparse(URL).path, reason="TEST_DATABASE_URL não definido"
)


@pytest.fixture
def conn():
    from ocean.shared.config import REPO_ROOT
    from ocean.storage.postgres.db import connect
    from ocean.storage.postgres.migrate import apply_migrations

    with connect(URL) as c:
        c.execute("DROP SCHEMA public CASCADE")
        c.execute("CREATE SCHEMA public")
        c.commit()
        apply_migrations(c, REPO_ROOT / "migrations")
        c.commit()
        yield c


def _settings(tmp_path):
    from ocean.shared.config import Settings

    return Settings(database_url=URL, data_dir=tmp_path)


def _put(folder, name, closures, areas):
    folder.mkdir(exist_ok=True)
    (folder / f"{name}_closures.csv").write_text(C_HEADER + closures, encoding="utf-8")
    (folder / f"{name}_areas.csv").write_text(A_HEADER + areas, encoding="utf-8")


@needs_db
def test_job_loads_is_idempotent_and_removes_stale(conn, tmp_path):
    from ocean.ingestion.jobs import mpa_closures

    folder = tmp_path / "defeso"
    garoupa = "k2,Garoupa,,PE,marine,11-01,02-28,,,Portaria 41/2018,,official,2026-08-12,\n"
    _put(folder, "defeso", LAGOSTA + garoupa, "k1,PE,2611606,Recife\nk2,PE,2611606,Recife\n")
    _put(
        folder,
        "curated",
        "c1,Caranguejo,Ucides cordatus,PE,marine,01-18,01-23,2026,,Portaria 45/2026,,official,2026-11-23,\n",
        "c1,PE,,\n",
    )

    first = mpa_closures.run(_settings(tmp_path))
    second = mpa_closures.run(_settings(tmp_path))
    assert first.rows == second.rows == 3 + 3
    count = lambda t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"]  # noqa: E731
    assert count("fishing_closures") == 3 and count("fishing_closure_areas") == 3
    year = conn.execute("SELECT year FROM fishing_closures WHERE species = 'Caranguejo'").fetchone()
    assert year["year"] == 2026

    # corrigir um período na origem: a linha antiga some, sem sobra
    _put(folder, "defeso", LAGOSTA.replace("04-30", "04-29"), "k1,PE,2611606,Recife\n")
    mpa_closures.run(_settings(tmp_path))
    ends = [r["prohibition_end"] for r in conn.execute("SELECT * FROM fishing_closures")]
    assert sorted(ends) == ["01-23", "04-29"]


@needs_db
def test_job_without_csvs_fails_with_hint(conn, tmp_path):
    from ocean.ingestion.jobs import mpa_closures

    with pytest.raises(FileNotFoundError, match="defeso_municipal"):
        mpa_closures.run(_settings(tmp_path))


def test_replace_all_refuses_empty_load():
    from ocean.storage.postgres import closures

    with pytest.raises(ValueError, match="carga vazia"):
        closures.replace_all(None, [])  # type: ignore[arg-type]


def test_same_common_name_different_scientific_name_are_distinct(tmp_path):
    bagres = (
        "k1,Bagre,Genidens genidens,RS,marine,12-15,03-31,,,IN MMA 17/2004,,official,2026-08-12,\n"
        "k2,Bagre,Genidens barbus,RS,marine,12-15,03-31,,,IN MMA 17/2004,,official,2026-08-12,\n"
    )
    c, a = _write(tmp_path, bagres, "k1,RS,,\nk2,RS,,\n")
    merged = dc.merge([dc.load_pair(c, a)])
    assert {m.closure.scientific_name for m in merged} == {"Genidens genidens", "Genidens barbus"}


def test_merge_treats_missing_scientific_name_as_same(tmp_path):
    c1, a1 = _write(tmp_path, LAGOSTA.replace("Panulirus argus", ""), "k1,PE,2611606,Recife\n", "t")
    c2, a2 = _write(tmp_path, LAGOSTA.replace("Panulirus argus", ""), "k1,RN,,\n", "u")
    assert len(dc.merge([dc.load_pair(c1, a1), dc.load_pair(c2, a2)])) == 1
