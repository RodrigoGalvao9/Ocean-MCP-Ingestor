"""Converte a tabela de defesos por município do MPA (texto extraído do PDF) em dois CSVs.

A tabela ("Lista nominal de municípios abrangidos ou limítrofes associados a cada período de
defeso vigente") tem uma linha por município, mas cada registro ocupa várias linhas no texto
(espécies longas quebram e períodos múltiplos vêm um por linha). Este script junta as linhas,
lê cada registro e agrupa por (ato, período, espécie).

Saídas (em --out-dir, só localmente: nada disso vai ao Git):
- defeso_closures.csv: um defeso por linha (formato de fishing_closures).
- defeso_areas.csv: municípios de cada defeso (formato de fishing_closure_areas).

Só o ambiente marinho é lido, e as espécies em --skip ficam de fora (o caranguejo-uçá tem
calendário próprio, mudado a cada ano, e a tabela traz datas defasadas dele).

    python -m ocean.ingestion.parsers.defeso_municipal TABELA.txt --out-dir data/defeso
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from importlib import resources
from pathlib import Path

from ocean.retrieval.structured.gazetteer import normalize

SOURCE_URL = (
    "https://www.gov.br/ibama/pt-br/assuntos/biodiversidade/biodiversidade-aquatica/"
    "periodos-de-defeso/defesos-marinhos"
)
DEFAULT_SKIP = ("Ucides cordatus",)
CLOSURE_FIELDS = [
    "key", "species", "scientific_name", "region", "environment", "prohibition_start",
    "prohibition_end", "year", "fishing_type", "legal_reference", "source_url", "source_type",
    "last_verified_at", "notes",
]  # fmt: skip
AREA_FIELDS = ["closure_key", "uf", "ibge_code", "municipality"]

_NOISE = {
    "MINISTÉRIO DA PESCA E AQUICULTURA",
    "ID PORTARIA PERIODO ESPECIE (S) AMBIENTE UF NOME MUNICIPIO COD_IBGE_MUN",
    "Lista nominal de municípios abrangidos ou limítrofes associados a cada período de defeso vigente",  # noqa: E501
    "",
}
_PERIOD = r"\d{1,2}/\d{1,2}-\d{1,2}/\d{1,2}"
_RECORD = re.compile(
    rf"^(?P<id>\d+) (?P<act>.+?) (?P<periods>{_PERIOD}(?: {_PERIOD})*) (?P<species>.+?) "
    r"(?P<env>Continental|Marinho) (?P<uf>[A-Z]{2}) (?P<mun>.+) (?P<ibge>\d{7})$"
)
_SCIENTIFIC = re.compile(r"^(?P<name>[^()]+?)\s*\((?P<sci>[A-Z][a-z]+ [a-z]+\.?[^()]*)\)\s*$")


def default_overrides_path() -> Path:
    return Path(str(resources.files("ocean").joinpath("data/defeso_overrides.csv")))


class DefesoTableError(ValueError):
    pass


@dataclass
class Closure:
    key: str
    act_id: str
    act: str
    species: str
    start: str
    end: str
    areas: dict[tuple[str, str], str] = field(default_factory=dict)  # (uf, ibge) -> município


def _md(day_month: str) -> str:
    day, month = (int(x) for x in day_month.split("/"))
    try:
        date(2000, month, day)  # 2000 é bissexto: aceita 29/02
    except ValueError:
        raise DefesoTableError(f"data inexistente: {day_month}") from None
    return f"{month:02d}-{day:02d}"


def split_period(period: str) -> tuple[str, str]:
    """'1/11-30/4' -> ('11-01', '04-30')."""
    start, end = period.split("-")
    return _md(start), _md(end)


def read_records(text: str) -> list[str]:
    """Junta as linhas quebradas: um registro termina na linha que acaba com o código IBGE."""
    records: list[str] = []
    buffer: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line in _NOISE:
            continue
        buffer.append(line)
        if re.search(r" \d{7}$", line):
            records.append(re.sub(r"\s+", " ", " ".join(buffer)))
            buffer = []
    if buffer:
        raise DefesoTableError(f"texto sobrando sem código IBGE no fim: {' '.join(buffer)[:120]}")
    return records


def load_overrides(path: Path) -> dict[tuple[str, str], tuple[str, str]]:
    """CSV `act_id,period,new_period,reason`: corrige (ou, com new_period vazio, descarta) um
    período da tabela que contradiz a norma. O motivo é obrigatório."""
    overrides: dict[tuple[str, str], tuple[str, str]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row["reason"].strip():
                raise DefesoTableError(f"correção sem motivo: ato {row['act_id']} {row['period']}")
            overrides[(row["act_id"].strip(), row["period"].strip())] = (
                row["new_period"].strip(),
                row["reason"].strip(),
            )
    return overrides


def parse(
    text: str,
    skip: tuple[str, ...] = DEFAULT_SKIP,
    overrides: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> tuple[list[Closure], list[str]]:
    """Devolve (defesos marinhos agrupados, avisos).

    Períodos com data inexistente (ex.: 31/11) são descartados e listados nos avisos, a menos
    que uma correção os substitua.
    """
    overrides = overrides or {}
    skip_keys = [normalize(s) for s in skip]
    warnings: list[str] = []
    repeated = 0
    closures: dict[tuple[str, str, str, str], Closure] = {}
    for record in read_records(text):
        m = _RECORD.match(record)
        if not m:
            raise DefesoTableError(f"registro não reconhecido: {record[:160]}")
        if m["env"] != "Marinho":
            continue
        species = m["species"].strip()
        if any(k in normalize(species) for k in skip_keys):
            continue
        for period in m["periods"].split():
            override = overrides.get((m["id"], period))
            if override is not None:
                if not override[0]:
                    continue  # descartado por correção
                period = override[0]
            try:
                start, end = split_period(period)
            except DefesoTableError as exc:
                msg = f"ato {m['id']} ({m['act'].strip()}): {exc}; período descartado"
                if msg not in warnings:
                    warnings.append(msg)
                continue
            ident = (m["id"], m["act"].strip(), species, period)
            closure = closures.get(ident)
            if closure is None:
                key = f"mun-{m['id']}-{start}-{end}"
                closure = closures[ident] = Closure(
                    key, m["id"], m["act"].strip(), species, start, end
                )
            area = (m["uf"], m["ibge"])
            if area in closure.areas:
                repeated += 1
            closure.areas[area] = m["mun"].strip()
    if repeated:
        warnings.append(f"{repeated} linhas de município repetidas na tabela (unificadas)")
    keys = [c.key for c in closures.values()]
    if len(keys) != len(set(keys)):
        # mesmo ato e período com espécies diferentes: desambigua pelo prefixo de espécie
        seen: dict[str, int] = {}
        for c in closures.values():
            seen[c.key] = seen.get(c.key, 0) + 1
            if seen[c.key] > 1:
                c.key = f"{c.key}-{seen[c.key]}"
    return list(closures.values()), warnings


def _split_species(species: str) -> tuple[str, str]:
    m = _SCIENTIFIC.match(species)
    return (m["name"].strip(), m["sci"].strip()) if m else (species, "")


def closure_row(c: Closure, verified_at: str, table_label: str) -> dict[str, str]:
    name, scientific = _split_species(c.species)
    ufs = sorted({uf for uf, _ in c.areas})
    return {
        "key": c.key,
        "species": name,
        "scientific_name": scientific,
        "region": ", ".join(ufs),
        "environment": "marine",
        "prohibition_start": c.start,
        "prohibition_end": c.end,
        "year": "",
        "fishing_type": "",
        "legal_reference": c.act,
        "source_url": SOURCE_URL,
        "source_type": "official",
        "last_verified_at": verified_at,
        "notes": f"Municípios: {table_label}. Inclui municípios abrangidos ou limítrofes.",
    }


def write_csvs(closures: list[Closure], out_dir: Path, verified_at: str, label: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "defeso_closures.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CLOSURE_FIELDS)
        writer.writeheader()
        for c in closures:
            writer.writerow(closure_row(c, verified_at, label))
    with (out_dir / "defeso_areas.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AREA_FIELDS)
        writer.writeheader()
        for c in closures:
            for (uf, ibge), mun in sorted(c.areas.items()):
                writer.writerow(
                    {"closure_key": c.key, "uf": uf, "ibge_code": ibge, "municipality": mun}
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("table", type=Path, help="texto extraído da tabela por município")
    parser.add_argument("--out-dir", type=Path, default=Path("data/defeso"))
    parser.add_argument("--verified-at", default="", help="AAAA-MM-DD da versão da tabela")
    parser.add_argument("--label", default="Tabela MPA por município", help="texto para as notas")
    parser.add_argument(
        "--overrides",
        type=Path,
        default=default_overrides_path(),
        help="CSV act_id,period,new_period,reason (correções da tabela pela norma)",
    )
    parser.add_argument("--skip", action="append", default=list(DEFAULT_SKIP), metavar="ESPÉCIE")
    args = parser.parse_args(argv)

    if not args.table.exists():
        print(f"{args.table} não existe.", file=sys.stderr)
        return 1
    try:
        overrides = load_overrides(args.overrides)
        closures, warnings = parse(
            args.table.read_text(encoding="utf-8"), tuple(args.skip), overrides
        )
    except DefesoTableError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    write_csvs(closures, args.out_dir, args.verified_at, args.label)
    for w in warnings[:20]:
        print(f"aviso: {w}")
    n_areas = sum(len(c.areas) for c in closures)
    print(f"{len(closures)} defesos marinhos, {n_areas} pares defeso-município -> {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
