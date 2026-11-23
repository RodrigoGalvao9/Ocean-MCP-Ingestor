"""Defeso: períodos em que a pesca de uma espécie é proibida, por lugar e data."""

import logging
from datetime import date as Date
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

import psycopg

from ocean.domain.models.fishing import FishingClosure
from ocean.domain.services import closures as calendar
from ocean.retrieval.structured import closures as closures_repo
from ocean.retrieval.structured import gazetteer
from ocean.retrieval.structured.gazetteer import normalize
from ocean.shared.provenance import Freshness, MaritimeDataResponse, Status, utcnow
from ocean.storage.postgres.db import connect

log = logging.getLogger(__name__)

SOURCE = "MPA e IBAMA: períodos de defeso marinhos"
SOURCE_URL = (
    "https://www.gov.br/ibama/pt-br/assuntos/biodiversidade/biodiversidade-aquatica/"
    "periodos-de-defeso/defesos-marinhos"
)
ATTRIBUTION = (
    "Períodos de defeso: Ministério da Pesca e Aquicultura (MPA) e IBAMA, conforme as normas "
    "citadas em cada item"
)
DEFAULT_DAYS_AHEAD = 90
MAX_DAYS_AHEAD = 366
MAX_OTHER = 15


def _today() -> Date:
    # America/Fortaleza = UTC-3 fixo (o Brasil não tem horário de verão)
    return utcnow().astimezone(ZoneInfo("America/Fortaleza")).date()


def _label(closure: FishingClosure) -> str:
    start, end = closure.prohibition_start, closure.prohibition_end
    return f"{start[3:]}/{start[:2]} a {end[3:]}/{end[:2]}"


def _scope(item: closures_repo.Coverage, place_name: str, uf: str) -> str | None:
    """Como o defeso alcança o lugar: nacional, estado, município, ou None (não alcança)."""
    if item.national:
        return "nacional"
    if item.state_wide:
        return f"estado ({uf})"
    if normalize(place_name) in {normalize(m) for m in item.municipalities}:
        return "município"
    return None


def _entry(item: closures_repo.Coverage, scope: str, day: Date) -> dict[str, Any]:
    c = item.closure
    current = next(
        (
            w
            for y in (day.year - 1, day.year)
            for w in calendar.windows(c, y)
            if w[0] <= day <= w[1]
        ),
        None,
    )
    upcoming = calendar.next_window(c, day)
    return {
        "species": c.species,
        "scientific_name": c.scientific_name,
        "period": _label(c),
        "period_start": c.prohibition_start,
        "period_end": c.prohibition_end,
        "year": c.year,
        "in_force": current is not None,
        "current_window": [d.isoformat() for d in current] if current else None,
        "next_window": [d.isoformat() for d in upcoming] if upcoming else None,
        "scope": scope,
        "fishing_type": c.fishing_type,
        "legal_reference": c.legal_reference,
        "source_url": c.source_url,
        "last_verified_at": c.last_verified_at.isoformat() if c.last_verified_at else None,
        "notes": c.notes,
    }


def get_fishing_closures(
    place: str,
    species: str | None = None,
    date: str | None = None,
    days_ahead: int = DEFAULT_DAYS_AHEAD,
) -> dict:
    """Defeso (período em que a pesca de uma espécie é proibida) no litoral de um lugar. Informe
    o NOME do lugar, por exemplo "Recife" ou "Natal". Opcional: species ("lagosta", "camarão",
    "caranguejo") para ver só aquela espécie, date=AAAA-MM-DD (padrão: hoje) e days_ahead (1 a
    366, padrão 90) para os defesos que começam nos próximos dias. Cada item traz a norma, o
    período e se está em vigor. Normas nacionais valem para todo o litoral. Serve de consulta
    de referência: confirme sempre no IBAMA ou no MPA antes de pescar ou vender."""
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

    try:
        day = _today() if date is None else Date.fromisoformat(date)
    except ValueError:
        return MaritimeDataResponse.unavailable(
            SOURCE, f"Data inválida '{date}'; use AAAA-MM-DD.", freshness=Freshness.REFERENCE
        ).to_tool_result()
    days_ahead = max(1, min(int(days_ahead), MAX_DAYS_AHEAD))

    try:
        with connect() as conn:
            covered = closures_repo.closures_for_uf(conn, found.uf)
    except (psycopg.Error, RuntimeError):
        log.exception("falha ao consultar defesos")
        return MaritimeDataResponse.unavailable(
            SOURCE,
            "O banco de defesos está temporariamente indisponível.",
            source_url=SOURCE_URL,
            freshness=Freshness.REFERENCE,
        ).to_tool_result()

    wanted = normalize(species) if species else None
    applicable: list[dict] = []
    others: list[dict] = []
    for item in covered:
        c = item.closure
        if wanted and wanted not in normalize(f"{c.species} {c.scientific_name or ''}"):
            continue
        scope = _scope(item, found.name, found.uf)
        if scope is None:
            others.append(
                {
                    "species": c.species,
                    "period": _label(c),
                    "legal_reference": c.legal_reference,
                    "year": c.year,
                }  # fmt: skip
            )
            continue
        applicable.append(_entry(item, scope, day))

    horizon = day + timedelta(days=days_ahead)
    in_force = [e for e in applicable if e["in_force"]]
    upcoming = [
        e
        for e in applicable
        if not e["in_force"]
        and e["next_window"]
        and (wanted or date_from(e["next_window"][0]) <= horizon)
    ]
    upcoming.sort(key=lambda e: e["next_window"][0])
    ended = [e for e in applicable if not e["in_force"] and not e["next_window"]]

    limitations = [
        "Os períodos seguem as normas publicadas e podem mudar por nova portaria; confirme no "
        "IBAMA ou no MPA antes de pescar, transportar ou vender. Não é orientação jurídica.",
    ]
    year_specific = [e for e in applicable if e["year"] is not None]
    if year_specific:
        years = sorted({e["year"] for e in year_specific})
        if day.year not in years or any(e in ended for e in year_specific):
            names = ", ".join(sorted({e["species"] for e in year_specific}))
            limitations.append(
                f"O defeso de {names} é definido por portaria a cada ano; só há dados de "
                f"{', '.join(map(str, years))}. Não há períodos cadastrados para depois disso."
            )
    if any(e["scope"] == "município" for e in applicable):
        limitations.append(
            "Itens de escopo 'município' vêm da lista de municípios abrangidos ou limítrofes do "
            "MPA; a norma original define a área exata."
        )
    if others:
        limitations.append(
            f"Há {len(others)} defeso(s) deste estado listados só para outros municípios; o lugar "
            "pedido não consta neles (pode pertencer a um município listado: confira o município)."
        )

    if not covered:
        status = Status.PARTIAL
        limitations.append(
            f"Não há defesos cadastrados para {found.uf}. Isso NÃO significa que a pesca esteja "
            "liberada: consulte o IBAMA ou o MPA."
        )
    elif wanted and not applicable:
        status = Status.PARTIAL
        limitations.append(
            f"Não encontrei defeso cadastrado de '{species}' para {found.label}. Isso NÃO "
            "prova que a pesca esteja liberada: consulte o IBAMA ou o MPA."
        )
    else:
        status = Status.OK

    verified = [e["last_verified_at"] for e in applicable if e["last_verified_at"]]
    return MaritimeDataResponse(
        status=status,
        source=SOURCE,
        source_url=SOURCE_URL,
        attribution=ATTRIBUTION,
        freshness=Freshness.REFERENCE,
        data={
            "requested_place": found.label,
            "uf": found.uf,
            "date": day.isoformat(),
            "species_filter": species,
            "in_force": in_force,
            "upcoming": upcoming,
            "ended_or_without_dates": ended,
            "listed_for_other_municipalities": others[:MAX_OTHER],
        },
        limitations=limitations,
        metadata={
            "days_ahead": days_ahead,
            "last_verified_at": max(verified) if verified else None,
            "closures_considered": len(covered),
        },
    ).to_tool_result()


def date_from(value: str) -> Date:
    return Date.fromisoformat(value)


def register(mcp) -> None:
    mcp.tool(name="get_fishing_closures")(get_fishing_closures)
