"""Condições do mar: vento, umidade, temperatura, ondas e temperatura da água (Open-Meteo)."""

import logging
from datetime import datetime, timedelta
from typing import Any

from ocean.domain.services.conditions import wave_summary, wind_summary
from ocean.retrieval.live import open_meteo
from ocean.retrieval.structured import gazetteer
from ocean.shared.http import SourceUnavailable
from ocean.shared.provenance import Freshness, MaritimeDataResponse, Status, utcnow
from ocean.storage.cache.redis_cache import Cache

log = logging.getLogger(__name__)

SOURCE = "Open-Meteo (previsão do tempo e Marine API)"
FRESH_TTL = 30 * 60  # cache de clima: 30 minutos
STALE_TTL = 6 * 3600  # cópia antiga, usada só se a fonte cair
MAX_HOURS = 48
STEP_HOURS = 3

_cache: Cache | None = None


def _get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache


def _base_limitations() -> list[str]:
    return [
        "Previsão de modelo numérico com resolução de cerca de 8 km; perto da costa pode "
        "não representar o ponto exato.",
        "Não é boletim oficial. Para decisões no mar, consulte os avisos da Marinha do Brasil.",
    ]


def _load_payload(place) -> tuple[dict[str, Any] | None, str]:
    """Devolve (envelope, origem): 'fresh', 'cache' ou 'stale'. Envelope None = sem dados."""
    cache = _get_cache()
    key = f"weather:{place.latitude:.2f}:{place.longitude:.2f}"
    cached = cache.get_json(key)
    if cached:
        return cached, "cache"
    try:
        payload = open_meteo.fetch(place.latitude, place.longitude)
    except SourceUnavailable as exc:
        log.warning(
            "open-meteo indisponível",
            extra={"place": place.label, "error": str(exc)},
            exc_info=True,
        )
        stale = cache.get_json(key + ":stale")
        if stale:
            return stale, "stale"
        return None, f"none:{exc.status_code or 'unknown'}"
    envelope = {"retrieved_at": utcnow().isoformat(), "payload": payload}
    cache.set_json(key, envelope, FRESH_TTL)
    cache.set_json(key + ":stale", envelope, STALE_TTL)
    return envelope, "fresh"


def _entry(values: dict[str, Any]) -> dict[str, Any]:
    return {
        "wind": wind_summary(
            values["wind_speed_ms"], values["wind_direction_deg"], values["wind_gust_ms"]
        ),
        "waves": wave_summary(
            values["wave_height_m"], values["wave_period_s"], values["wave_direction_deg"]
        ),
        "humidity_pct": values["humidity_pct"],
        "air_temperature_c": values["air_temperature_c"],
        "sea_temperature_c": values["sea_temperature_c"],
    }


def _forecast(payload: dict[str, Any], reference: datetime, hours: int) -> list[dict[str, Any]]:
    times = (payload["weather"].get("hourly") or {}).get("time") or []
    limit = reference + timedelta(hours=hours)
    out: list[dict[str, Any]] = []
    for index, raw in enumerate(times):
        moment = open_meteo.parse_time(raw)
        if moment <= reference or moment > limit:
            continue
        if (moment - reference) % timedelta(hours=STEP_HOURS) != timedelta(0):
            continue
        out.append(
            {"time": moment.isoformat(), **_entry(open_meteo.snapshot(payload, index, "hourly"))}
        )
    return out


def get_marine_conditions(place: str, hours: int = 0) -> dict:
    """Condições do mar em um lugar: vento (nós, km/h, escala Beaufort), rajadas, umidade,
    temperatura do ar, altura e período das ondas e temperatura da água. Informe o NOME do
    lugar, por exemplo "Recife", "Porto Seguro" ou "Santos" (nunca coordenadas). Use
    hours=0 para as condições atuais; use hours entre 3 e 48 para incluir a previsão das
    próximas horas, de 3 em 3 horas. Não use para marés: para isso use get_tide_table."""
    hours = max(0, min(int(hours), MAX_HOURS))
    found = gazetteer.resolve(place)
    if found is None:
        return MaritimeDataResponse(
            status=Status.PARTIAL,
            source="Lugares conhecidos pelo Ocean",
            freshness=Freshness.REFERENCE,
            data={
                "requested_place": place,
                "known_places": [p.label for p in gazetteer.all_places()],
            },
            limitations=[
                f"Não reconheci o lugar '{place}'. Peça ao usuário um dos lugares conhecidos, "
                "ou o município litorâneo mais próximo."
            ],
        ).to_tool_result()

    envelope, origin = _load_payload(found)
    if envelope is None:
        if origin == "none:429":
            reason = (
                "O Open-Meteo limitou temporariamente as requisições deste serviço (HTTP 429). "
                "Tente novamente mais tarde ou configure uma cota adequada para produção."
            )
        else:
            reason = "A fonte de condições do mar está temporariamente indisponível."
        return MaritimeDataResponse.unavailable(
            SOURCE,
            reason,
            source_url=open_meteo.SOURCE_URL,
            metadata={"resolved_location": found.model_dump()},
        ).to_tool_result()

    payload = envelope["payload"]
    current_block = payload["weather"].get("current") or {}
    time_raw = current_block.get("time")
    reference = open_meteo.parse_time(time_raw) if time_raw else None

    data: dict[str, Any] = {
        "resolved_location": {**found.model_dump(), "label": found.label},
        "current": _entry(open_meteo.snapshot(payload, 0, "current")),
    }
    if hours and reference:
        data["forecast"] = _forecast(payload, reference, hours)

    limitations = _base_limitations()
    status = Status.OK
    if origin == "stale":
        status = Status.STALE
        limitations.append(
            "A fonte não respondeu agora; os valores vêm de uma consulta anterior "
            "(veja retrieved_at)."
        )
    elif data["current"]["waves"] is None:
        status = Status.PARTIAL
        limitations.append("Não há dados de ondas para este ponto; só vento e clima.")

    return MaritimeDataResponse(
        status=status,
        source=SOURCE,
        source_url=open_meteo.SOURCE_URL,
        attribution=open_meteo.ATTRIBUTION,
        license="CC BY 4.0; API gratuita, uso não comercial",
        retrieved_at=datetime.fromisoformat(envelope["retrieved_at"]),
        data_timestamp=reference,
        freshness=Freshness.LIVE if origin == "fresh" else Freshness.RECENT,
        data=data,
        limitations=limitations,
        metadata={"origin": origin, "forecast_step_hours": STEP_HOURS},
    ).to_tool_result()


def register(mcp) -> None:
    mcp.tool(name="get_marine_conditions")(get_marine_conditions)
