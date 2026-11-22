import contextlib
from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from ocean.domain.models.tide import TideEvent, TideStation
from ocean.domain.services.geo import haversine_km
from ocean.domain.services.tides import significant_extremes
from ocean.server.tools import tide_table as tt

NOW = datetime(2026, 3, 10, 12, 0, tzinfo=UTC)
RECIFE = TideStation(
    id="recife-pe", name="Porto do Recife", uf="PE", latitude=-8.0567, longitude=-34.8667,
    chart_number="902", timezone="Etc/GMT+3",
)  # fmt: skip
SALVADOR = TideStation(
    id="salvador-ba", name="Porto de Salvador", uf="BA", latitude=-12.9733, longitude=-38.5167,
    timezone="Etc/GMT+3",
)  # fmt: skip


def ev(hours: float, kind: str, height: float, station="recife-pe", edition=63) -> TideEvent:
    return TideEvent(
        station_id=station,
        at=NOW + timedelta(hours=hours),
        kind=kind,
        height_m=height,
        edition=edition,
    )


def cycle(station="recife-pe") -> list[TideEvent]:
    """Ciclo regular em volta de NOW: baixa-mar -2h, preamar +4h, baixa-mar +10h, ..."""
    out = []
    for i in range(-3, 14):
        hours = -2 + 6.2 * i
        high = i % 2 == 1
        out.append(ev(hours, "high" if high else "low", 2.1 if high else 0.3, station))
    return out


def test_haversine():
    assert haversine_km(-8.0476, -34.8770, -8.0089, -34.8553) == pytest.approx(4.9, abs=0.5)
    assert haversine_km(-8.05, -34.88, -12.97, -38.50) == pytest.approx(675, abs=15)
    assert haversine_km(1, 1, 1, 1) == 0


def test_ripples_are_merged_but_real_cycles_stay():
    # Santos, 11/01/2026 (tábua da DHN): oscilação de 1 cm entre 0.80 e 0.81
    raw = [(1.28, "low", 0.64), (8.27, "high", 0.81), (9.95, "low", 0.80), (11.23, "high", 0.81),
           (15.35, "low", 0.54), (20.73, "high", 0.98)]  # fmt: skip
    kept = significant_extremes([ev(h, k, v) for h, k, v in raw])
    assert [(e.kind, e.height_m) for e in kept] == [
        ("low", 0.64),
        ("high", 0.81),
        ("low", 0.54),
        ("high", 0.98),
    ]
    assert [e.kind for e in kept] == ["low", "high", "low", "high"]


def test_ripples_double_peak_keeps_higher():
    kept = significant_extremes(
        [
            ev(0, "low", 0.2),
            ev(3, "high", 1.5),
            ev(4, "low", 1.45),
            ev(5, "high", 1.6),
            ev(10, "low", 0.1),
        ]
    )
    assert [(e.kind, e.height_m) for e in kept] == [("low", 0.2), ("high", 1.6), ("low", 0.1)]


def test_missing_event_in_table_is_not_merged_away():
    # duas baixa-mares seguidas, 12 h separadas: falta a preamar do meio (caso real de Salvador)
    kept = significant_extremes([ev(0, "low", 0.3), ev(12, "low", 0.3), ev(18, "high", 2.0)])
    assert [e.kind for e in kept] == ["low", "low", "high"]


class FakeConn(contextlib.AbstractContextManager):
    def __exit__(self, *exc):
        return False


@pytest.fixture
def fake_db(monkeypatch):
    state = {
        "stations": [RECIFE, SALVADOR],
        "events": {"recife-pe": cycle(), "salvador-ba": cycle("salvador-ba")},
    }
    monkeypatch.setattr(tt, "_now", lambda: NOW)
    monkeypatch.setattr(tt, "connect", lambda: FakeConn())
    monkeypatch.setattr(tt.tides_repo, "stations_with_events", lambda conn, a, b: state["stations"])
    monkeypatch.setattr(
        tt.tides_repo, "events_between",
        lambda conn, station_id, a, b: [e for e in state["events"][station_id] if a <= e.at <= b],
    )  # fmt: skip
    return state


def test_recife_rising_with_next_events(fake_db):
    r = tt.get_tide_table("Recife")
    assert r["status"] == "ok" and r["freshness"] == "reference"
    assert r["data"]["station"]["id"] == "recife-pe" and r["data"]["distance_km"] < 30
    cur = r["data"]["current"]
    assert cur["phase"] == "rising" and cur["phase_pt"] == "enchente"
    assert cur["previous"]["kind"] == "low" and cur["next_high"]["in_minutes"] == 252
    assert cur["next_low"]["kind_pt"] == "baixa-mar"
    assert cur["next_high"]["time_local"] == "2026-03-10 13:12"  # 16:12 UTC, UTC-3
    assert r["data"]["events"][0]["time_utc"] >= NOW.isoformat()
    assert r["attribution"].startswith("Previsão de marés: Marinha") and r["metadata"][
        "editions"
    ] == [63]


def test_hours_clamped_and_window(fake_db):
    r = tt.get_tide_table("Recife", hours=1)
    events = r["data"]["events"]
    assert all(e["in_minutes"] <= 6 * 60 for e in events)
    wide = tt.get_tide_table("Recife", hours=99999)
    assert wide["metadata"]["window_utc"][1] == (NOW + timedelta(hours=168)).isoformat()


def test_date_mode_uses_local_day_of_station(fake_db):
    r = tt.get_tide_table("Recife", date="2026-03-10")
    assert r["status"] == "ok"
    assert {e["time_local"][:10] for e in r["data"]["events"]} == {"2026-03-10"}


def test_date_in_another_period_has_no_current_phase(fake_db):
    fake_db["stations"] = []
    r = tt.get_tide_table("Recife", date="2027-01-05")
    assert r["status"] == "partial" and "2026" in r["limitations"][0]


def test_invalid_date(fake_db):
    assert tt.get_tide_table("Recife", date="10/03/2026")["status"] == "unavailable"


def test_far_station_is_refused_with_nearest_named(fake_db):
    fake_db["stations"] = [SALVADOR]
    r = tt.get_tide_table("Recife")
    assert r["status"] == "partial" and r["data"]["nearest_station"]["name"] == "Porto de Salvador"
    assert "events" not in r["data"] and r["data"]["distance_km"] > 600


def test_medium_distance_warns(fake_db):
    fake_db["stations"] = [RECIFE]
    r = tt.get_tide_table("Porto de Suape")  # ~ 47 km de Recife
    assert r["status"] == "ok" and any("km do local pedido" in x for x in r["limitations"])


def test_missing_event_makes_phase_unknown(fake_db):
    events = [e for e in cycle() if not (-1 < (e.at - NOW).total_seconds() / 3600 < 6)]
    # sem a preamar seguinte: anterior (baixa-mar) e próximo (baixa-mar) são iguais
    fake_db["events"]["recife-pe"] = events
    r = tt.get_tide_table("Recife")
    assert r["data"]["current"]["phase"] == "unknown"
    assert any("fase da maré não pôde" in x for x in r["limitations"])


def test_unknown_place(fake_db):
    r = tt.get_tide_table("Atlântida")
    assert r["status"] == "partial" and "Recife (PE)" in r["data"]["known_places"]


def test_database_down_is_unavailable(monkeypatch):
    def boom():
        raise psycopg.OperationalError("down")

    monkeypatch.setattr(tt, "connect", boom)
    r = tt.get_tide_table("Recife")
    assert r["status"] == "unavailable" and "temporariamente" in r["limitations"][0]


def test_ripples_are_reported(fake_db):
    extra = [ev(2.0, "high", 0.38), ev(2.5, "low", 0.35)]  # ondulação entre a baixa-mar e a preamar
    fake_db["events"]["recife-pe"] = sorted(cycle() + extra, key=lambda e: e.at)
    r = tt.get_tide_table("Recife")
    assert r["metadata"]["ignored_minor_events"] == 2
    assert any("agrupadas" in x for x in r["limitations"])
