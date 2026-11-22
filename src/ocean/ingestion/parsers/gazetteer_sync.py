"""Propõe entradas do gazetteer a partir das estações de maré.

As estações (tabela `tide_stations` do Postgres, carregadas dos PDFs da DHN) são portos com
coordenadas conhecidas. Este script sugere os que ainda não estão em
`ocean/data/gazetteer.csv`, para que "maré em Natal" ache a estação mais próxima de qualquer
"maré em Natal" ache a estação mais próxima de qualquer lugar do gazetteer.

Por padrão só MOSTRA o que adicionaria (simulação). Com `--write` acrescenta as linhas ao fim do
gazetteer, sem tocar nas existentes. Nomes que já existem (em qualquer UF) são pulados: o
índice do gazetteer é por nome normalizado, então um nome repetido em outra UF seria ambíguo.

    python -m ocean.ingestion.parsers.gazetteer_sync [--write]

Usa DATABASE_URL (somente leitura basta). `--stations ARQUIVO.csv` lê de um CSV no lugar do banco.
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from ocean.retrieval.structured.gazetteer import normalize
from ocean.storage.postgres.db import connect

FIELDS = ["name", "uf", "kind", "latitude", "longitude", "aliases"]
LAT_RANGE = (-35.0, 6.0)  # mesma faixa validada em tests/test_places.py
LON_RANGE = (-75.0, -30.0)
_PORT_PREFIX = re.compile(r"^(porto|terminal)\s+(de|do|da|dos|das)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class Proposal:
    row: dict[str, str]
    station_id: str


@dataclass(frozen=True)
class Skipped:
    station_id: str
    name: str
    reason: str


def base_name(station_name: str) -> str:
    """'Porto de Natal' -> 'Natal'; 'Porto de Suape - Cais 4' -> 'Suape'."""
    name = station_name.split(" - ", 1)[0].strip()
    return _PORT_PREFIX.sub("", name).strip()


def default_gazetteer_path() -> Path:
    return Path(str(resources.files("ocean").joinpath("data/gazetteer.csv")))


def read_gazetteer_names(path: Path) -> dict[str, str]:
    """Nome ou apelido normalizado -> UF, para todas as entradas existentes."""
    known: dict[str, str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            for name in [row["name"], *filter(None, row["aliases"].split("|"))]:
                known[normalize(name)] = row["uf"]
    return known


def propose(
    stations: list[dict[str, str]], known: dict[str, str]
) -> tuple[list[Proposal], list[Skipped]]:
    proposals: list[Proposal] = []
    skipped: list[Skipped] = []
    seen = dict(known)
    for st in stations:
        sid, original = st["id"], st["name"]
        name = base_name(original)
        key = normalize(name)
        try:
            lat, lon = float(st["latitude"]), float(st["longitude"])
        except ValueError:
            skipped.append(Skipped(sid, original, "coordenadas inválidas"))
            continue
        if not (LAT_RANGE[0] < lat < LAT_RANGE[1] and LON_RANGE[0] < lon < LON_RANGE[1]):
            skipped.append(Skipped(sid, original, "fora da faixa do Brasil"))
            continue
        if not key:
            skipped.append(Skipped(sid, original, "nome vazio"))
            continue
        if key in seen:
            same = seen[key] == st["uf"]
            skipped.append(
                Skipped(sid, original, "já existe" if same else f"nome já usado em {seen[key]}")
            )
            continue
        aliases = [original] if normalize(original) != key else []
        row = {
            "name": name,
            "uf": st["uf"],
            "kind": "porto",
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "aliases": "|".join(aliases),
        }
        seen[key] = st["uf"]
        for alias in aliases:
            seen[normalize(alias)] = st["uf"]
        proposals.append(Proposal(row, sid))
    return proposals, skipped


def load_stations_db(database_url: str | None = None) -> list[dict[str, str]]:
    with connect(database_url) as conn:
        rows = conn.execute(
            "SELECT id, name, uf, latitude, longitude FROM tide_stations ORDER BY id"
        ).fetchall()
    return [{k: str(v) for k, v in row.items()} for row in rows]


def load_stations_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def append_rows(path: Path, proposals: list[Proposal]) -> None:
    text = path.read_text(encoding="utf-8")
    with path.open("a", encoding="utf-8", newline="") as handle:
        if text and not text.endswith("\n"):
            handle.write("\n")
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        for p in proposals:
            writer.writerow(p.row)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--stations", type=Path, help="CSV de estações (padrão: ler do banco)")
    parser.add_argument("--gazetteer", type=Path, default=default_gazetteer_path())
    parser.add_argument("--write", action="store_true", help="grava no gazetteer (padrão: simula)")
    args = parser.parse_args(argv)

    if args.stations is not None:
        if not args.stations.exists():
            print(f"{args.stations} não existe.", file=sys.stderr)
            return 1
        stations = load_stations_csv(args.stations)
    else:
        try:
            stations = load_stations_db()
        except Exception as exc:  # DATABASE_URL ausente, rede, tabela inexistente
            print(f"Não consegui ler as estações do banco: {exc}", file=sys.stderr)
            return 1

    proposals, skipped = propose(stations, read_gazetteer_names(args.gazetteer))
    for p in proposals:
        r = p.row
        print(f"+ {r['name']} ({r['uf']}) {r['latitude']},{r['longitude']}  [{p.station_id}]")
    for s in skipped:
        print(f"- {s.name} [{s.station_id}]: {s.reason}")
    print(f"{len(proposals)} a adicionar, {len(skipped)} puladas.")

    if args.write and proposals:
        append_rows(args.gazetteer, proposals)
        print(f"Gravado em {args.gazetteer}.")
    elif proposals:
        print("Simulação: use --write para gravar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
