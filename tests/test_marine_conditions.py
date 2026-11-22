import httpx
import pytest

from ocean.retrieval.live import open_meteo
from ocean.server.tools import marine_conditions as mc
from ocean.shared.http import SourceUnavailable
from ocean.storage.cache.redis_cache import Cache

TIMES = [f"2026-11-21T{h:02d}:00" for h in range(0, 24)] + [
    f"2026-11-22T{h:02d}:00" for h in range(0, 24)
]


def _weather():
    n = len(TIMES)
    block = {
        "time": TIMES,
        "wind_speed_10m": [5.0] * n,
        "wind_direction_10m": [90.0] * n,
        "wind_gusts_10m": [8.0] * n,
        "relative_humidity_2m": [80] * n,
        "temperature_2m": [27.0] * n,
    }
    return {"current": {**{k: v[12] for k, v in block.items() if k != "time"}, "time": TIMES[12]},
            "hourly": block}  # fmt: skip


def _marine(waves=True):
    n = len(TIMES)
    value = 1.4 if waves else None
    block = {
        "time": TIMES,
        "wave_height": [value] * n,
        "wave_period": [8.0 if waves else None] * n,
        "wave_direction": [110.0 if waves else None] * n,
        "sea_surface_temperature": [28.0] * n,
    }
    current = {k: v[12] for k, v in block.items() if k != "time"}
    return {"current": {**current, "time": TIMES[12]}, "hourly": block}


class FakeCache:
    def __init__(self):
        self.store = {}

    def get_json(self, key):
        return self.store.get(key)

    def set_json(self, key, value, ttl_seconds):
        self.store[key] = value


def test_cache_works_in_memory_without_redis():
    cache = Cache(url="")
    cache.set_json("weather:test", {"ok": True}, 60)

    assert cache.get_json("weather:test") == {"ok": True}


@pytest.fixture
def cache(monkeypatch):
    fake = FakeCache()
    monkeypatch.setattr(mc, "_cache", fake)
    return fake


def _patch_fetch(monkeypatch, waves=True, fail=False):
    def fake(lat, lon, client=None):
        if fail:
            raise SourceUnavailable("fora do ar")
        return {"weather": _weather(), "marine": _marine(waves)}

    monkeypatch.setattr(open_meteo, "fetch", fake)


def test_ok_contract_and_interpretation(monkeypatch, cache):
    _patch_fetch(monkeypatch)
    r = mc.get_marine_conditions("Recife")
    assert r["status"] == "ok" and r["freshness"] == "live"
    assert r["data"]["resolved_location"]["label"] == "Recife (PE)"
    wind = r["data"]["current"]["wind"]
    assert wind["speed_knots"] == 9.7 and wind["direction_from"] == "L"
    assert wind["beaufort_force"] == 3  # 9,7 nós: brisa fraca
    assert r["data"]["current"]["waves"]["height_m"] == 1.4
    assert r["attribution"] and r["source_url"] and r["data_timestamp"].startswith("2026-11-21T12")
    assert "forecast" not in r["data"]


def test_forecast_every_three_hours(monkeypatch, cache):
    _patch_fetch(monkeypatch)
    r = mc.get_marine_conditions("Recife", hours=9)
    times = [e["time"][11:16] for e in r["data"]["forecast"]]
    assert times == ["15:00", "18:00", "21:00"]


def test_hours_is_clamped(monkeypatch, cache):
    _patch_fetch(monkeypatch)
    r = mc.get_marine_conditions("Recife", hours=9999)
    assert len(r["data"]["forecast"]) <= 48 // mc.STEP_HOURS


def test_second_call_uses_cache(monkeypatch, cache):
    _patch_fetch(monkeypatch)
    mc.get_marine_conditions("Recife")
    _patch_fetch(monkeypatch, fail=True)
    r = mc.get_marine_conditions("Recife")
    assert r["status"] == "ok" and r["metadata"]["origin"] == "cache"


def test_stale_when_source_fails(monkeypatch, cache):
    _patch_fetch(monkeypatch)
    mc.get_marine_conditions("Recife")
    key = next(k for k in cache.store if not k.endswith(":stale"))
    del cache.store[key]  # expirou o cache novo, sobrou a cópia antiga
    _patch_fetch(monkeypatch, fail=True)
    r = mc.get_marine_conditions("Recife")
    assert r["status"] == "stale" and any("anterior" in x for x in r["limitations"])


def test_unavailable_without_cache(monkeypatch, cache):
    _patch_fetch(monkeypatch, fail=True)
    r = mc.get_marine_conditions("Recife")
    assert r["status"] == "unavailable" and r["data"] == {}


def test_rate_limit_is_reported_without_retrying(monkeypatch, cache):
    def fake(lat, lon, client=None):
        raise SourceUnavailable("limite", status_code=429)

    monkeypatch.setattr(open_meteo, "fetch", fake)
    r = mc.get_marine_conditions("Recife")
    assert r["status"] == "unavailable"
    assert "HTTP 429" in r["limitations"][0]


def test_partial_without_waves(monkeypatch, cache):
    _patch_fetch(monkeypatch, waves=False)
    r = mc.get_marine_conditions("Recife")
    assert r["status"] == "partial" and r["data"]["current"]["waves"] is None


def test_unknown_place_lists_known_places(cache):
    r = mc.get_marine_conditions("Atlântida")
    assert r["status"] == "partial" and "Recife (PE)" in r["data"]["known_places"]


def test_fetch_builds_requests_without_sea_level():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = _weather() if "api.open-meteo" in request.url.host else _marine()
        return httpx.Response(200, json=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    payload = open_meteo.fetch(-8.05, -34.88, client=client)
    assert payload["marine"] is not None and len(seen) == 2
    assert all("sea_level" not in str(r.url) for r in seen)
    assert "wind_speed_unit=ms" in str(seen[0].url) and "timezone=UTC" in str(seen[0].url)


def test_fetch_survives_marine_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        if "marine" in request.url.host:
            return httpx.Response(400, json={"error": True})
        return httpx.Response(200, json=_weather())

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert open_meteo.fetch(-8.05, -34.88, client=client)["marine"] is None
