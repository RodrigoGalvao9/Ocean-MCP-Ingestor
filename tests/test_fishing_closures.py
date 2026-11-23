# ruff: noqa: E501
import contextlib
from datetime import UTC, date, datetime

import psycopg
import pytest

from ocean.domain.models.fishing import FishingClosure
from ocean.retrieval.structured.closures import Coverage
from ocean.server.tools import fishing_closures as fc


def closure(species, start, end, year=None, ref="Portaria X", sci=None):
    return FishingClosure(
        species=species, scientific_name=sci, prohibition_start=start, prohibition_end=end,
        year=year, legal_reference=ref, last_verified_at=date(2026, 11, 23),
    )  # fmt: skip


LAGOSTA = Coverage(
    closure("Lagosta vermelha", "11-01", "04-30", sci="Panulirus argus"), state_wide=True
)
GAROUPA = Coverage(closure("Garoupa-verdadeira", "11-01", "02-28"), national=True)
PARGO = Coverage(closure("Pargo", "12-15", "04-30"), state_wide=True)
CARANGUEJO = Coverage(closure("Caranguejo-uçá", "01-18", "01-23", year=2026), state_wide=True)
CAMARAO_SSA = Coverage(
    closure("Camarão-rosa", "04-01", "05-15"), municipalities=["Salvador", "Lauro de Freitas"]
)
CAMARAO_OUTROS = Coverage(closure("Camarão-rosa", "09-15", "10-31"), municipalities=["Ilhéus"])


class FakeConn(contextlib.AbstractContextManager):
    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake(monkeypatch):
    state = {
        "covered": [LAGOSTA, GAROUPA, PARGO, CARANGUEJO, CAMARAO_SSA, CAMARAO_OUTROS],
        "uf": [],
    }
    monkeypatch.setattr(fc, "_today", lambda: date(2026, 11, 23))
    monkeypatch.setattr(fc, "connect", lambda: FakeConn())

    def fake_for_uf(conn, uf):
        state["uf"].append(uf)
        return state["covered"]

    monkeypatch.setattr(fc.closures_repo, "closures_for_uf", fake_for_uf)
    return state


def names(entries):
    return [e["species"] for e in entries]


def test_today_in_force_and_upcoming(fake):
    r = fc.get_fishing_closures("Recife")
    assert r["status"] == "ok" and fake["uf"] == ["PE"]
    assert names(r["data"]["in_force"]) == ["Lagosta vermelha", "Garoupa-verdadeira"]
    assert names(r["data"]["upcoming"]) == ["Pargo"]  # começa em 15/12, dentro de 90 dias
    lagosta = r["data"]["in_force"][0]
    assert lagosta["scope"] == "estado (PE)" and lagosta["current_window"] == [
        "2026-11-01",
        "2027-04-30",
    ]
    assert r["data"]["in_force"][1]["scope"] == "nacional"
    assert r["metadata"]["last_verified_at"] == "2026-11-23"


def test_upcoming_respects_days_ahead(fake):
    r = fc.get_fishing_closures("Recife", days_ahead=10)
    assert names(r["data"]["upcoming"]) == []
    assert names(fc.get_fishing_closures("Recife", days_ahead=30)["data"]["upcoming"]) == ["Pargo"]


def test_species_filter_matches_accents_and_scientific_name(fake):
    assert names(fc.get_fishing_closures("Recife", species="LAGOSTA")["data"]["in_force"]) == [
        "Lagosta vermelha"
    ]
    assert fc.get_fishing_closures("Recife", species="panulirus")["data"]["in_force"]
    r = fc.get_fishing_closures("Recife", species="caranguejo-uca", date="2026-01-20")
    assert names(r["data"]["in_force"]) == ["Caranguejo-uçá"]


def test_species_filter_shows_next_window_even_if_far(fake):
    r = fc.get_fishing_closures("Salvador", species="camarao", date="2026-11-23")
    [item] = r["data"]["upcoming"]
    assert item["next_window"] == ["2027-04-01", "2027-05-15"] and item["scope"] == "município"


def test_municipal_scope_only_matches_listed_municipality(fake):
    r = fc.get_fishing_closures("Salvador", date="2026-04-10")
    assert names(r["data"]["in_force"]) == ["Lagosta vermelha", "Pargo", "Camarão-rosa"] and (
        r["data"]["listed_for_other_municipalities"][0]["period"] == "15/09 a 31/10"
    )
    assert any("outros municípios" in x for x in r["limitations"])
    assert any("municípios abrangidos" in x for x in r["limitations"])


def test_year_specific_closure_without_data_for_year(fake):
    r = fc.get_fishing_closures("Recife", species="caranguejo", date="2027-01-20")
    assert r["data"]["in_force"] == [] and names(r["data"]["ended_or_without_dates"]) == [
        "Caranguejo-uçá"
    ]
    assert any("só há dados de 2026" in x for x in r["limitations"])


def test_year_specific_after_window_ended_in_same_year(fake):
    r = fc.get_fishing_closures("Recife", species="caranguejo")  # hoje: 23/11/2026
    assert any("só há dados de 2026" in x for x in r["limitations"])


def test_species_without_match_is_partial_and_never_says_free(fake):
    r = fc.get_fishing_closures("Recife", species="tainha")
    assert r["status"] == "partial"
    assert any("NÃO prova" in x for x in r["limitations"])


def test_uf_without_data_is_partial(fake):
    fake["covered"] = []
    r = fc.get_fishing_closures("Recife")
    assert r["status"] == "partial" and any("NÃO significa" in x for x in r["limitations"])


def test_unknown_place_and_invalid_date(fake):
    assert "known_places" in fc.get_fishing_closures("Atlântida")["data"]
    r = fc.get_fishing_closures("Recife", date="ontem")
    assert r["status"] == "unavailable"


def test_database_down(monkeypatch, fake):
    def boom():
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(fc, "connect", boom)
    assert fc.get_fishing_closures("Recife")["status"] == "unavailable"


def test_registered_with_server():
    from ocean.server.tools import register_all

    registered = []

    class FakeMcp:
        def tool(self, name):
            registered.append(name)
            return lambda fn: fn

    register_all(FakeMcp())
    assert "get_fishing_closures" in registered


def test_today_uses_brasilia_offset(monkeypatch):
    monkeypatch.setattr(fc, "utcnow", lambda: datetime(2026, 11, 24, 1, 30, tzinfo=UTC))
    assert fc._today() == date(2026, 11, 23)  # 01:30 UTC ainda é dia 23 em UTC-3
