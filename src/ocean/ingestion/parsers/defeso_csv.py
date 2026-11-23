"""Lê os CSVs de defeso (do parser da tabela do MPA e/ou do arquivo curado) e valida."""

import csv
import re
from datetime import date
from pathlib import Path

from ocean.domain.models.fishing import FishingClosure, LoadedClosure

_UF = re.compile(r"^[A-Z]{2}$")  # "BR" = norma nacional (vale para todo o litoral)
_IBGE = re.compile(r"^(\d{7})?$")
_CLOSURE_COLUMNS = {
    "key", "species", "scientific_name", "region", "environment", "prohibition_start",
    "prohibition_end", "year", "fishing_type", "legal_reference", "source_url", "source_type",
    "last_verified_at", "notes",
}  # fmt: skip
_AREA_COLUMNS = {"closure_key", "uf", "ibge_code", "municipality"}


class DefesoCsvError(ValueError):
    pass


def _read(path: Path, columns: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = columns - set(reader.fieldnames or [])
        if missing:
            raise DefesoCsvError(f"{path.name}: faltam colunas {sorted(missing)}")
        return list(reader)


def _closure(row: dict[str, str], source: str) -> FishingClosure:
    try:
        verified = date.fromisoformat(row["last_verified_at"]) if row["last_verified_at"] else None
        closure = FishingClosure(
            species=row["species"].strip(),
            scientific_name=row["scientific_name"].strip() or None,
            region=row["region"].strip() or None,
            environment=row["environment"].strip(),
            prohibition_start=row["prohibition_start"].strip(),
            prohibition_end=row["prohibition_end"].strip(),
            year=int(row["year"]) if row["year"].strip() else None,
            fishing_type=row["fishing_type"].strip() or None,
            legal_reference=row["legal_reference"].strip(),
            source_url=row["source_url"].strip() or None,
            source_type=row["source_type"].strip(),
            last_verified_at=verified,
            notes=row["notes"].strip() or None,
        )
    except ValueError as exc:
        raise DefesoCsvError(f"{source} {row.get('key')}: {exc}") from exc
    for label, value in (("início", closure.prohibition_start), ("fim", closure.prohibition_end)):
        try:
            date(2000, int(value[:2]), int(value[3:5]))
        except (ValueError, IndexError):
            raise DefesoCsvError(f"{source} {row['key']}: {label} inválido ({value!r})") from None
    if closure.environment not in {"marine", "continental"}:
        raise DefesoCsvError(f"{source} {row['key']}: ambiente inválido ({closure.environment!r})")
    if not closure.species or not closure.legal_reference:
        raise DefesoCsvError(f"{source} {row['key']}: espécie e norma são obrigatórias")
    return closure


def load_pair(closures_path: Path, areas_path: Path) -> list[LoadedClosure]:
    """Lê um par closures/areas. Toda linha de area precisa apontar para um defeso existente e
    todo defeso precisa de ao menos uma área."""
    by_key: dict[str, LoadedClosure] = {}
    for row in _read(closures_path, _CLOSURE_COLUMNS):
        if row["key"] in by_key:
            raise DefesoCsvError(f"{closures_path.name}: chave repetida {row['key']}")
        by_key[row["key"]] = LoadedClosure(_closure(row, closures_path.name))
    for row in _read(areas_path, _AREA_COLUMNS):
        target = by_key.get(row["closure_key"])
        if target is None:
            raise DefesoCsvError(f"{areas_path.name}: defeso desconhecido {row['closure_key']}")
        uf, ibge = row["uf"].strip(), row["ibge_code"].strip()
        if not _UF.match(uf) or not _IBGE.match(ibge):
            raise DefesoCsvError(f"{areas_path.name}: área inválida {uf!r}/{ibge!r}")
        target.areas[(uf, ibge)] = row["municipality"].strip() or None
    empty = [k for k, v in by_key.items() if not v.areas]
    if empty:
        raise DefesoCsvError(f"{closures_path.name}: defesos sem área: {empty[:5]}")
    return list(by_key.values())


def merge(groups: list[list[LoadedClosure]]) -> list[LoadedClosure]:
    """Junta vários pares. Defesos com a mesma chave natural (norma, espécie, período, ano) viram
    um só, com a união das áreas; vale o último grupo (o curado vence a tabela)."""
    merged: dict[tuple, LoadedClosure] = {}
    for group in groups:
        for item in group:
            existing = merged.get(item.natural_key)
            if existing is not None:
                item.areas = {**existing.areas, **item.areas}
            merged[item.natural_key] = item
    return list(merged.values())
