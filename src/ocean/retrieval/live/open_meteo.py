"""Cliente do Open-Meteo (previsão do tempo e Marine API).

Gratuito e sem chave para uso NÃO comercial; atribuição obrigatória (CC BY 4.0).
`sea_level_height_msl` NÃO é usado: referência global, não serve como tábua de maré.
"""

from datetime import UTC, datetime
from typing import Any

import httpx

from ocean.shared.http import build_client, request

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
SOURCE_URL = "https://open-meteo.com/"
ATTRIBUTION = "Dados meteorológicos por Open-Meteo.com (CC BY 4.0)"

_WEATHER_VARS = (
    "wind_speed_10m,wind_direction_10m,wind_gusts_10m,relative_humidity_2m,temperature_2m"
)
_MARINE_VARS = "wave_height,wave_period,wave_direction,sea_surface_temperature"


def _params(lat: float, lon: float, variables: str, extra: dict[str, Any]) -> dict[str, Any]:
    return {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "current": variables,
        "hourly": variables,
        "forecast_days": 3,
        "timezone": "UTC",
        **extra,
    }


def parse_time(value: str) -> datetime:
    """Open-Meteo devolve 'AAAA-MM-DDTHH:MM' já em UTC (pedimos timezone=UTC)."""
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def fetch(lat: float, lon: float, client: httpx.Client | None = None) -> dict[str, Any]:
    """Consulta previsão (vento, umidade, temperatura) e ondas. Levanta SourceUnavailable se o
    serviço de VENTO falhar; falha só na parte marítima devolve `marine=None`."""
    owned = client is None
    client = client or build_client()
    try:
        weather = request(
            client,
            "GET",
            FORECAST_URL,
            params=_params(lat, lon, _WEATHER_VARS, {"wind_speed_unit": "ms"}),
        ).json()
        try:
            marine = request(
                client, "GET", MARINE_URL, params=_params(lat, lon, _MARINE_VARS, {})
            ).json()
        except Exception:
            marine = None
    finally:
        if owned:
            client.close()
    return {"weather": weather, "marine": marine}


def _at(block: dict[str, Any] | None, name: str, index: int) -> float | None:
    if not block:
        return None
    values = block.get(name)
    if not values or index >= len(values):
        return None
    return values[index]


def snapshot(payload: dict[str, Any], index: int, kind: str) -> dict[str, Any]:
    """Valores de um instante: 'current' (um valor) ou 'hourly' (posição `index` da lista)."""

    def get(source: str, name: str) -> float | None:
        block = payload[source]
        if block is None:
            return None
        if kind == "current":
            value = (block.get("current") or {}).get(name)
            return value
        return _at(block.get("hourly"), name, index)

    return {
        "wind_speed_ms": get("weather", "wind_speed_10m"),
        "wind_direction_deg": get("weather", "wind_direction_10m"),
        "wind_gust_ms": get("weather", "wind_gusts_10m"),
        "humidity_pct": get("weather", "relative_humidity_2m"),
        "air_temperature_c": get("weather", "temperature_2m"),
        "wave_height_m": get("marine", "wave_height"),
        "wave_period_s": get("marine", "wave_period"),
        "wave_direction_deg": get("marine", "wave_direction"),
        "sea_temperature_c": get("marine", "sea_surface_temperature"),
    }
