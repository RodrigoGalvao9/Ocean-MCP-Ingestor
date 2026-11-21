"""Gazetteer: resolve o nome de um lugar (texto livre) em coordenadas.

O LLM nunca informa latitude e longitude: ele passa o NOME e o servidor resolve aqui.
A tabela (`ocean/data/gazetteer.csv`) começa pelo Nordeste piloto (PE, BA, SE, RN, MA) mais
Santos e Paranaguá. As coordenadas são aproximadas (centro do município ou do porto) e
servem a consultas de previsão de baixa resolução; conferir com a base do IBGE antes de
usá-las como posição precisa.
"""

import csv
import re
import unicodedata
from functools import lru_cache
from importlib import resources

from ocean.domain.models.places import Place

_STATE_NAMES = {
    "pernambuco": "PE", "bahia": "BA", "sergipe": "SE",
    "rio grande do norte": "RN", "maranhao": "MA", "sao paulo": "SP", "parana": "PR",
}  # fmt: skip


def normalize(text: str) -> str:
    """Minúsculas, sem acentos e sem pontuação: 'São Luís, MA' -> 'sao luis ma'."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()


@lru_cache(maxsize=1)
def _load() -> tuple[tuple[Place, ...], dict[str, Place]]:
    path = resources.files("ocean").joinpath("data/gazetteer.csv")
    places: list[Place] = []
    index: dict[str, Place] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            place = Place(
                name=row["name"],
                uf=row["uf"],
                kind=row["kind"],
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
            )
            places.append(place)
            names = [row["name"], *filter(None, row["aliases"].split("|"))]
            for name in names:
                index[normalize(name)] = place
    return tuple(places), index


def all_places() -> list[Place]:
    return list(_load()[0])


def _strip_state(query: str) -> tuple[str, str | None]:
    """Separa um estado no fim da consulta ('recife pe', 'recife pernambuco')."""
    for state_name, uf in _STATE_NAMES.items():
        if query.endswith(" " + state_name):
            return query[: -len(state_name)].strip(), uf
    parts = query.rsplit(" ", 1)
    if len(parts) == 2 and len(parts[1]) == 2:
        return parts[0], parts[1].upper()
    return query, None


def resolve(text: str) -> Place | None:
    """Devolve o lugar citado em `text`, ou None se não houver correspondência única.

    Aceita 'Recife', 'Recife, PE', 'maré em Santos amanhã' (procura o nome como expressão
    inteira dentro do texto, preferindo o nome mais longo).
    """
    _, index = _load()
    query = normalize(text)
    if not query:
        return None
    if query in index:
        return index[query]

    stripped, uf = _strip_state(query)
    if uf not in {p.uf for p in _load()[0]}:
        uf = None  # a última palavra não era um estado conhecido
    else:
        query = stripped
    if stripped in index and uf is not None:
        return index[stripped] if index[stripped].uf == uf else None

    padded = f" {query} "
    found = {key: place for key, place in index.items() if f" {key} " in padded}
    if uf is not None:
        found = {key: place for key, place in found.items() if place.uf == uf}
    if not found:
        return None
    longest = max(len(key) for key in found)
    best = {place.label: place for key, place in found.items() if len(key) == longest}
    return next(iter(best.values())) if len(best) == 1 else None
