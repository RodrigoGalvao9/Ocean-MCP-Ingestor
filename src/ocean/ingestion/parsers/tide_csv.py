"""Leitura do CSV padronizado de estações e eventos de maré (ver data/tides/README.md).

É a porta de entrada comum: um parser de PDF da DHN deve gerar este mesmo formato, e tábuas
digitadas à mão (plano B) o usam diretamente.
"""

import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ocean.domain.models.tide import TideEvent, TideStation

MIN_HEIGHT_M = -1.0
MAX_HEIGHT_M = 9.0  # maior que as maiores marés do litoral brasileiro; pega erro de digitação
_KINDS = {"high", "low"}


class TideDataError(ValueError):
    """Linha ou arquivo inválido (a mensagem indica arquivo e linha)."""


def load_stations(path: Path) -> list[TideStation]:
    stations: list[TideStation] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=2):
            try:
                stations.append(
                    TideStation(
                        id=row["id"].strip(),
                        name=row["name"].strip(),
                        uf=row["uf"].strip() or None,
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        chart_number=row["chart_number"].strip() or None,
                        timezone=row["timezone"].strip() or "America/Sao_Paulo",
                        datum_note=row["datum_note"].strip() or None,
                    )
                )
                ZoneInfo(stations[-1].timezone)
            except (KeyError, ValueError) as exc:
                raise TideDataError(f"{path.name}:{number}: {exc}") from exc
    ids = [s.id for s in stations]
    if len(ids) != len(set(ids)):
        raise TideDataError(f"{path.name}: ids de estação repetidos")
    return stations


def parse_events(path: Path, stations: dict[str, TideStation]) -> list[TideEvent]:
    """Lê um CSV de eventos e converte o horário legal da estação para UTC."""
    events: list[TideEvent] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for number, row in enumerate(csv.DictReader(handle), start=2):
            where = f"{path.name}:{number}"
            station = stations.get((row.get("station_id") or "").strip())
            if station is None:
                raise TideDataError(f"{where}: estação desconhecida '{row.get('station_id')}'")
            kind = (row.get("kind") or "").strip().lower()
            if kind not in _KINDS:
                raise TideDataError(f"{where}: kind deve ser 'high' ou 'low', veio '{kind}'")
            try:
                height = float(row["height_m"])
                local = datetime.fromisoformat(row["local_datetime"].strip())
                edition_raw = (row.get("edition") or "").strip()
                edition = int(edition_raw) if edition_raw else None
            except (KeyError, ValueError) as exc:
                raise TideDataError(f"{where}: {exc}") from exc
            if local.tzinfo is not None:
                raise TideDataError(f"{where}: use horário local da estação, sem fuso")
            if not MIN_HEIGHT_M <= height <= MAX_HEIGHT_M:
                raise TideDataError(
                    f"{where}: altura {height} m fora de [{MIN_HEIGHT_M}, {MAX_HEIGHT_M}]"
                )
            at = local.replace(tzinfo=ZoneInfo(station.timezone)).astimezone(ZoneInfo("UTC"))
            events.append(
                TideEvent(station_id=station.id, at=at, kind=kind, height_m=height, edition=edition)
            )
    return events


def check_alternation(events: list[TideEvent]) -> list[str]:
    """Avisos para eventos consecutivos do mesmo tipo (sinal de linha faltando) por estação."""
    warnings: list[str] = []
    by_station: dict[str, list[TideEvent]] = {}
    for event in events:
        by_station.setdefault(event.station_id, []).append(event)
    for station_id, items in by_station.items():
        ordered = sorted(items, key=lambda e: e.at)
        for before, after in zip(ordered, ordered[1:], strict=False):
            if before.kind == after.kind:
                warnings.append(
                    f"{station_id}: dois eventos '{after.kind}' seguidos "
                    f"({before.at:%Y-%m-%d %H:%M} e {after.at:%Y-%m-%d %H:%M} UTC)"
                )
    return warnings
