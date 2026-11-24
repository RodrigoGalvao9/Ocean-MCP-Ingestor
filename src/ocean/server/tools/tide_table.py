"""Tábua de marés: estação mais próxima, fase da maré e próximas preamares e baixa-mares."""

import logging
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import psycopg

from ocean.domain.models.tide import TideEvent, TideStation
from ocean.domain.services.geo import haversine_km
from ocean.domain.services.tides import MIN_SWING_M, significant_extremes, tide_state
from ocean.retrieval.structured import gazetteer
from ocean.retrieval.structured import tides as tides_repo
from ocean.shared.provenance import Freshness, MaritimeDataResponse, Status, utcnow
from ocean.storage.postgres.db import connect_readonly as connect  # servidor: só leitura

log = logging.getLogger(__name__)

SOURCE = "Marinha do Brasil, DHN: Tábuas das Marés"
SOURCE_URL = "https://www.marinha.mil.br/chm/tabuas-de-mare"
ATTRIBUTION = "Previsão de marés: Marinha do Brasil, Diretoria de Hidrografia e Navegação (DHN)"
KIND_PT = {"high": "preamar", "low": "baixa-mar"}

# Limites de distância até a estação: escolha do Ocean (a DHN não fixa um raio de validade).
NEAR_KM = 30.0
FAR_KM = 100.0
DEFAULT_HOURS = 36
MAX_HOURS = 168
MARGIN = timedelta(hours=14)  # eventos extras antes e depois, para a fase nas bordas


def _now() -> datetime:
    return utcnow()


def _event(event: TideEvent, zone: ZoneInfo, now: datetime) -> dict[str, Any]:
    local = event.at.astimezone(zone)
    return {
        "time_utc": event.at.isoformat(),
        "time_local": local.strftime("%Y-%m-%d %H:%M"),
        "kind": event.kind,
        "kind_pt": KIND_PT[event.kind],
        "height_m": round(event.height_m, 2),
        "in_minutes": round((event.at - now).total_seconds() / 60),
    }


def _limitations(station: TideStation, distance_km: float, ignored: int) -> list[str]:
    notes = [
        "Previsão astronômica: não inclui efeitos do tempo (vento, pressão, chuva e vazão de "
        "rios), que podem mudar horários e alturas. Não substitui a tábua oficial da DHN.",
        f"Alturas em metros acima do nível de redução da carta náutica; horários em horário "
        f"legal da estação ({station.timezone}).",
    ]
    if distance_km > NEAR_KM:
        notes.append(
            f"A estação '{station.name}' fica a {distance_km:.0f} km do local pedido; em baías, "
            "estuários e rios os horários e alturas podem ser bem diferentes."
        )
    if ignored:
        notes.append(
            f"{ignored} oscilações menores que {MIN_SWING_M:.2f} m da tábua foram agrupadas ao "
            "extremo mais próximo."
        )
    return notes


def _window(
    day: str | None, hours: int, zone_by_station: bool = False
) -> tuple[datetime, datetime]:
    now = _now()
    if day is None:
        return now, now + timedelta(hours=hours)
    chosen = datetime.fromisoformat(day).date()
    # O dia local depende da estação; aqui usa UTC-3 (todas as estações do país hoje, exceto
    # as ilhas oceânicas e o Norte) só para delimitar a busca; o filtro final usa o fuso da
    # estação.
    start = datetime.combine(chosen, time.min, tzinfo=ZoneInfo("Etc/GMT+3"))
    return start, start + timedelta(days=1)


def get_tide_table(place: str, hours: int = DEFAULT_HOURS, date: str | None = None) -> dict:
    """Marés em um lugar do litoral: estação da DHN mais próxima, fase atual (enchente ou
    vazante) e as preamares e baixa-mares das próximas horas. Informe o NOME do lugar, por
    exemplo "Recife", "Salvador" ou "Santos". Use hours (6 a 168, padrão 36) para a janela a
    partir de agora, ou date=AAAA-MM-DD para o dia inteiro (horário local da estação). A
    tábua cobre apenas o ano publicado (2026). Para vento e ondas use get_marine_conditions."""
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
                f"Não reconheci o lugar '{place}'. Peça um dos lugares conhecidos ou o município "
                "litorâneo mais próximo."
            ],
        ).to_tool_result()

    hours = max(6, min(int(hours), MAX_HOURS))
    try:
        start, end = _window(date, hours)
    except ValueError:
        return MaritimeDataResponse.unavailable(
            SOURCE, f"Data inválida '{date}'; use AAAA-MM-DD.", freshness=Freshness.REFERENCE
        ).to_tool_result()

    try:
        with connect() as conn:
            candidates = tides_repo.stations_with_events(conn, start - MARGIN, end + MARGIN)
            if not candidates:
                return MaritimeDataResponse(
                    status=Status.PARTIAL,
                    source=SOURCE,
                    source_url=SOURCE_URL,
                    attribution=ATTRIBUTION,
                    freshness=Freshness.REFERENCE,
                    data={"requested_place": found.label},
                    limitations=[
                        "Não há previsão de marés carregada para esse período; a tábua "
                        "cobre apenas o ano de 2026."
                    ],
                ).to_tool_result()
            station, distance_km = min(
                (
                    (s, haversine_km(found.latitude, found.longitude, s.latitude, s.longitude))
                    for s in candidates
                ),
                key=lambda pair: pair[1],
            )
            if distance_km > FAR_KM:
                return MaritimeDataResponse(
                    status=Status.PARTIAL,
                    source=SOURCE,
                    source_url=SOURCE_URL,
                    attribution=ATTRIBUTION,
                    freshness=Freshness.REFERENCE,
                    data={
                        "requested_place": found.label,
                        "nearest_station": {"name": station.name, "uf": station.uf},
                        "distance_km": round(distance_km),
                    },
                    limitations=[
                        f"A estação mais próxima ({station.name}) fica a {distance_km:.0f} km: "
                        "longe demais para estimar a maré neste local com segurança."
                    ],
                ).to_tool_result()
            events = tides_repo.events_between(conn, station.id, start - MARGIN, end + MARGIN)
    except (psycopg.Error, RuntimeError):
        log.exception("falha ao consultar marés")
        return MaritimeDataResponse.unavailable(
            SOURCE,
            "O banco de marés está temporariamente indisponível.",
            source_url=SOURCE_URL,
            freshness=Freshness.REFERENCE,
        ).to_tool_result()

    now = _now()
    zone = ZoneInfo(station.timezone)
    significant = significant_extremes(events)
    ignored = len(events) - len(significant)
    state = tide_state(now, significant)
    if date is not None:  # o dia pedido é o dia LOCAL da estação
        local_day = datetime.fromisoformat(date).date()
        window = [e for e in significant if e.at.astimezone(zone).date() == local_day]
    else:
        window = [e for e in significant if start <= e.at <= end]

    current = None
    upcoming = [e for e in (state.next_high, state.next_low) if e is not None]
    following = min(upcoming, key=lambda e: e.at) if upcoming else None
    # Só descreve "agora" se os eventos em volta realmente cercam o instante atual (consulta de
    # outro dia ou fora da tábua não tem fase atual).
    if (
        state.previous is not None
        and following is not None
        and following.at - state.previous.at <= timedelta(hours=14)
    ):
        current = {
            "phase": state.phase,
            "phase_pt": state.phase_pt,
            "previous": _event(state.previous, zone, now) if state.previous else None,
            "next_high": _event(state.next_high, zone, now) if state.next_high else None,
            "next_low": _event(state.next_low, zone, now) if state.next_low else None,
        }
    editions = sorted({e.edition for e in events if e.edition is not None})
    status = Status.OK if window else Status.PARTIAL
    limitations = _limitations(station, distance_km, ignored)
    if not window:
        limitations.append("Não há eventos de maré nessa janela.")
    if state.phase == "unknown" and current:
        limitations.append("A fase da maré não pôde ser determinada (evento ausente na tábua).")

    return MaritimeDataResponse(
        status=status,
        source=SOURCE,
        source_url=SOURCE_URL,
        attribution=ATTRIBUTION,
        freshness=Freshness.REFERENCE,
        data_timestamp=now,
        data={
            "requested_place": found.label,
            "station": {
                "id": station.id,
                "name": station.name,
                "uf": station.uf,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "chart_number": station.chart_number,
                "timezone": station.timezone,
            },
            "distance_km": round(distance_km, 1),
            "current": current,
            "events": [_event(e, zone, now) for e in window],
        },
        limitations=limitations,
        metadata={
            "editions": editions,
            "min_swing_m": MIN_SWING_M,
            "ignored_minor_events": ignored,
            "window_utc": [
                start.astimezone(ZoneInfo("UTC")).isoformat(),
                end.astimezone(ZoneInfo("UTC")).isoformat(),
            ],
        },
    ).to_tool_result()


def register(mcp) -> None:
    mcp.tool(name="get_tide_table")(get_tide_table)
