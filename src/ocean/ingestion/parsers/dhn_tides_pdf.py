"""Parser das páginas de "Tábuas das Marés" da DHN (um PDF por porto, 3 páginas).

Layout observado nas edições de 2026 (63ª edição): cada página tem 4 meses; cada mês ocupa
duas colunas (dias 1 a 16 e 17 a 31), cada uma com "HORA ALT(m)". Cada dia tem 3 ou 4 linhas:
a primeira traz o número do dia, a segunda o dia da semana. A tábua NÃO rotula preamar e
baixa-mar: o tipo é deduzido pela alternância dos extremos e conferido com as alturas.

Uso:
    python -m ocean.ingestion.parsers.dhn_tides_pdf recife.pdf suape.pdf \
        --stations data/tide_stations.csv --out-dir data/tides

Gera um CSV de eventos por porto e cria ou atualiza a linha da estação, no formato de
docs/mares-csv.md. Termina com código 1 se encontrar erros (avisos não bloqueiam).
"""

import argparse
import calendar
import csv
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

Word = dict[str, Any]  # {"text": str, "x0": float, "top": float}

MONTHS = [
    "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]  # fmt: skip
UF_BY_STATE = {
    "PERNAMBUCO": "PE", "BAHIA": "BA", "SERGIPE": "SE", "RIO GRANDE DO NORTE": "RN",
    "MARANHAO": "MA", "CEARA": "CE", "PARAIBA": "PB", "ALAGOAS": "AL", "PIAUI": "PI",
    "PARA": "PA", "AMAPA": "AP", "ESPIRITO SANTO": "ES", "RIO DE JANEIRO": "RJ",
    "SAO PAULO": "SP", "PARANA": "PR", "SANTA CATARINA": "SC", "RIO GRANDE DO SUL": "RS",
}  # fmt: skip
_TIME = re.compile(r"^\d{4}$")
_HEIGHT = re.compile(r"^-?\d{1,2}[.,]\d{2}$")  # alguns PDFs usam vírgula decimal
_DAY = re.compile(r"^\d{1,2}$")
_GROUP_MARGIN = 24.0  # o número do dia fica ~16 pt à esquerda de "HORA"
_LINE_TOLERANCE = 3.0
# O dia da semana ("DOM") às vezes cola no horário que vem logo depois ("DOM1040").
_WEEKDAY_GLUED = re.compile(r"^[A-ZÀ-Ý]{3}(?=\d{4}$)")
MAX_READINGS_PER_DAY = 10
MIN_GAP = timedelta(hours=2, minutes=30)
MAX_GAP = timedelta(hours=9, minutes=30)


def _ascii(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@dataclass
class Header:
    name: str
    state: str | None
    year: int
    latitude: float
    longitude: float
    utc_offset_hours: float
    mean_level_m: float
    chart_number: str | None


@dataclass
class RawDay:
    month: int
    day: int
    readings: list[tuple[str, float]]  # (HHMM, altura)


@dataclass
class ParsedTable:
    header: Header
    days: list[RawDay]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class TideRow:
    local: datetime  # horário legal da estação, sem fuso
    kind: str
    height_m: float


def _lines(words: list[Word]) -> list[list[Word]]:
    lines: list[list[Word]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and word["top"] - lines[-1][0]["top"] <= _LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def _coordinate(text: str, label: str) -> float:
    match = re.search(label + r"\s+(\d+)°\s*(\d+)'(?:\.(\d+))?\s*([NSEWO])", text)
    if not match:
        raise ValueError(f"{label} não encontrada no cabeçalho")
    degrees, minutes, decimals, hemisphere = match.groups()
    value = int(degrees) + (int(minutes) + float(f"0.{decimals}" if decimals else 0)) / 60
    return round(-value if hemisphere in "SWO" else value, 4)


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def parse_header(text: str) -> Header:
    title = re.search(
        r"^(?P<name>.+?)\s*(?:\((?P<state>[^)]*)\))?\s*-\s*(?P<year>\d{4})\s*$", text, re.M
    )
    if not title:
        raise ValueError("título da página não encontrado")
    state = title.group("state")
    if state:
        state = re.sub(r"^ESTADO D[AEO]\s+", "", state.strip(), flags=re.I)
    fuso = re.search(r"Fuso\s+(UTC\s*)?([+-]?\d+(?:[.,]\d+)?)", text)
    mean = re.search(r"N[ií]vel M[ée]dio\s+(-?\d+(?:[.,]\d+)?)\s*m", text)
    chart = re.search(r"Carta\s+(\S+)", text)
    if not fuso or not mean:
        raise ValueError("fuso horário ou nível médio não encontrados no cabeçalho")
    latitude, longitude = _coordinate(text, "Latitude"), _coordinate(text, "Longitude")
    offset = _number(fuso.group(2))
    if not fuso.group(1):
        # Sem "UTC", "Fuso +03.0" segue a convenção náutica: horas a SOMAR ao horário local
        # para chegar a UTC, ou seja, UTC-3.
        offset = -offset
    if abs(offset - longitude / 15) > 2.0:
        raise ValueError(f"fuso UTC{offset:+.1f} incompatível com a longitude {longitude}")
    return Header(
        name=title.group("name").strip(),
        state=state,
        year=int(title.group("year")),
        latitude=latitude,
        longitude=longitude,
        utc_offset_hours=offset,
        mean_level_m=_number(mean.group(1)),
        chart_number=chart.group(1) if chart else None,
    )


def parse_page(words: list[Word]) -> tuple[Header, list[RawDay], list[str]]:
    """Lê uma página: cabeçalho e os dias de 4 meses. Devolve também erros de leitura."""
    horas = sorted((w for w in words if w["text"] == "HORA"), key=lambda w: w["x0"])
    if len(horas) != 8:
        raise ValueError(f"esperava 8 colunas 'HORA' e encontrei {len(horas)}")
    table_top = horas[0]["top"]

    header_words = [w for w in words if w["top"] < table_top - 5]
    header_text = "\n".join(" ".join(w["text"] for w in line) for line in _lines(header_words))
    header = parse_header(header_text)

    month_words = [
        w for w in words if _ascii(w["text"]).lower() in MONTHS and abs(w["top"] - table_top) < 20
    ]
    month_words.sort(key=lambda w: w["x0"])
    if len(month_words) != 4:
        raise ValueError(f"esperava 4 meses na página e encontrei {len(month_words)}")
    months = [MONTHS.index(_ascii(w["text"]).lower()) + 1 for w in month_words]

    errors: list[str] = []
    days: list[RawDay] = []
    starts = [w["x0"] for w in horas]
    for index, start in enumerate(starts):
        left = start - _GROUP_MARGIN
        right = starts[index + 1] - _GROUP_MARGIN if index + 1 < len(starts) else float("inf")
        group = [w for w in words if left <= w["x0"] < right and w["top"] > table_top + 3]
        month = months[index // 2]
        current: RawDay | None = None
        for line in _lines(group):
            tokens = [_WEEKDAY_GLUED.sub("", w["text"]) for w in line]
            if _DAY.match(tokens[0]) and line[0]["x0"] < start - 5:
                current = RawDay(month=month, day=int(tokens[0]), readings=[])
                days.append(current)
                tokens = tokens[1:]
            if current is None:
                continue
            numbers = [t for t in tokens if _TIME.match(t) or _HEIGHT.match(t)]
            pairs = list(zip(numbers[::2], numbers[1::2], strict=False))
            valid = len(numbers) % 2 == 0 and all(
                _TIME.match(t) and _HEIGHT.match(h) for t, h in pairs
            )
            if not valid:
                errors.append(f"mês {month} dia {current.day}: linha ilegível {tokens}")
                continue
            current.readings.extend((t, _number(h)) for t, h in pairs)
    # Conferência independente do layout: todo horário (HHMM) da área da tabela precisa ter
    # virado uma leitura; se sobrar ou faltar token, algo foi lido errado.
    tokens = [_WEEKDAY_GLUED.sub("", w["text"]) for w in words if w["top"] > table_top + 3]
    time_tokens = sum(bool(_TIME.match(t)) for t in tokens)
    height_tokens = sum(bool(_HEIGHT.match(t)) for t in tokens)
    parsed = sum(len(day.readings) for day in days)
    if not time_tokens == height_tokens == parsed:
        errors.append(
            f"leituras lidas ({parsed}) diferem dos horários ({time_tokens}) "
            f"e alturas ({height_tokens}) da página"
        )
    return header, days, errors


def extract_page_words(page) -> list[Word]:
    """Palavras com posição (PyMuPDF). O pdfplumber/pdfminer perdia as duas primeiras linhas
    de alguns PDFs da DHN (título e número da página), por isso não é usado aqui."""
    return [{"text": w[4], "x0": w[0], "top": w[1]} for w in page.get_text("words")]


def parse_pdf(path: Path) -> ParsedTable:
    import pymupdf

    headers: list[Header] = []
    days: list[RawDay] = []
    errors: list[str] = []
    with pymupdf.open(path) as pdf:
        for number, page in enumerate(pdf, start=1):
            try:
                header, page_days, page_errors = parse_page(extract_page_words(page))
            except ValueError as exc:
                errors.append(f"{path.name} página {number}: {exc}")
                continue
            headers.append(header)
            days.extend(page_days)
            errors.extend(f"página {number}: {e}" for e in page_errors)
    if not headers:
        raise ValueError(f"{path.name}: nenhuma página legível")
    first = headers[0]
    for other in headers[1:]:
        if other != first:
            errors.append("o cabeçalho muda entre as páginas")
    table = ParsedTable(header=first, days=days, errors=errors)
    return table


def build_rows(table: ParsedTable) -> list[TideRow]:
    """Valida o calendário, deduz preamar e baixa-mar e confere com as alturas.
    Acrescenta erros e avisos em `table`."""
    header, errors, warnings = table.header, table.errors, table.warnings
    seen: dict[tuple[int, int], RawDay] = {}
    for day in table.days:
        key = (day.month, day.day)
        if key in seen:
            errors.append(f"dia repetido: {day.day:02d}/{day.month:02d}")
        seen[key] = day
    for month in range(1, 13):
        for day in range(1, calendar.monthrange(header.year, month)[1] + 1):
            if (month, day) not in seen:
                errors.append(f"dia ausente: {day:02d}/{month:02d}")
    for month, day in seen:
        if day > calendar.monthrange(header.year, month)[1]:
            errors.append(f"dia inexistente: {day:02d}/{month:02d}")

    raw: list[tuple[datetime, float]] = []
    for (month, day_number), day in sorted(seen.items()):
        if not 1 <= day_number <= calendar.monthrange(header.year, month)[1]:
            continue
        # A DHN lista todo extremo local, inclusive pequenas ondulações (Santos, Itaguaí, Angra:
        # 5 a 8 por dia). 3 ou 4 é o normal; fora disso só avisa. Zero ou mais de 10 é falha.
        if not 1 <= len(day.readings) <= MAX_READINGS_PER_DAY:
            errors.append(f"{day_number:02d}/{month:02d}: {len(day.readings)} leituras")
        elif len(day.readings) not in (3, 4):
            warnings.append(f"{day_number:02d}/{month:02d}: {len(day.readings)} leituras")
        for hhmm, height in day.readings:
            hour, minute = int(hhmm[:2]), int(hhmm[2:])
            if hour > 23 or minute > 59:
                errors.append(f"{day_number:02d}/{month:02d}: horário inválido {hhmm}")
                continue
            raw.append((datetime.combine(date(header.year, month, day_number), datetime.min.time())
                        .replace(hour=hour, minute=minute), height))  # fmt: skip
    raw.sort()
    if len(raw) < 2:
        errors.append("leituras insuficientes")
        return []

    rows = _classify(raw, header.mean_level_m)
    _check_rows(rows, errors, warnings)
    return rows


def _classify(raw: list[tuple[datetime, float]], mean: float) -> list[TideRow]:
    """Preamar é o extremo maior que os vizinhos; baixa-mar, o menor. Quando falta um evento
    na própria tábua, o vizinho deixa de ser extremo e vale o nível médio como desempate."""
    rows: list[TideRow] = []
    for i, (at, height) in enumerate(raw):
        neighbours = [raw[j][1] for j in (i - 1, i + 1) if 0 <= j < len(raw)]
        if all(height > n for n in neighbours):
            kind = "high"
        elif all(height < n for n in neighbours):
            kind = "low"
        else:
            kind = "high" if height > mean else "low"
        rows.append(TideRow(local=at, kind=kind, height_m=height))
    return rows


def _check_rows(rows: list[TideRow], errors: list[str], warnings: list[str]) -> None:
    """Problemas da própria tábua (evento ausente) viram AVISOS; a carga continua e o
    cálculo da fase da maré trata a lacuna como 'indeterminada'."""
    for before, after in zip(rows, rows[1:], strict=False):
        stamp = f"{before.local:%d/%m %H:%M} e {after.local:%d/%m %H:%M}"
        if before.kind == after.kind:
            warnings.append(f"{stamp}: dois eventos '{after.kind}' seguidos (evento ausente?)")
        gap = after.local - before.local
        if not MIN_GAP <= gap <= MAX_GAP:
            warnings.append(f"{stamp}: intervalo de {gap}")


# --- saída em CSV -----------------------------------------------------------------------

STATION_FIELDS = [
    "id",
    "name",
    "uf",
    "latitude",
    "longitude",
    "chart_number",
    "timezone",
    "datum_note",
]
EVENT_FIELDS = ["station_id", "local_datetime", "kind", "height_m", "edition"]
_SMALL_WORDS = {"de", "do", "da", "dos", "das", "e"}
DATUM_NOTE = "Alturas referidas ao nível de redução da carta; horário legal"


def _title(name: str) -> str:
    words = name.lower().split()
    return " ".join(w if (i and w in _SMALL_WORDS) else w.capitalize() for i, w in enumerate(words))


def station_id(header: Header, uf: str | None) -> str:
    base = re.sub(r"^porto\s+d[aeo]s?\s+", "", _ascii(header.name).lower())
    slug = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return f"{slug}-{uf.lower()}" if uf else slug


def utc_zone(offset_hours: float) -> str:
    """Fuso fixo (o Brasil não tem horário de verão desde 2019): UTC-3 -> Etc/GMT+3."""
    if offset_hours != int(offset_hours):
        raise ValueError(f"fuso não inteiro: {offset_hours}")
    hours = int(offset_hours)
    return "Etc/GMT" + (f"+{-hours}" if hours < 0 else f"-{hours}" if hours > 0 else "")


def station_row(header: Header, uf: str | None) -> dict[str, str]:
    return {
        "id": station_id(header, uf),
        "name": _title(header.name),
        "uf": uf or "",
        "latitude": f"{header.latitude:.4f}",
        "longitude": f"{header.longitude:.4f}",
        "chart_number": header.chart_number or "",
        "timezone": utc_zone(header.utc_offset_hours),
        "datum_note": DATUM_NOTE,
    }


def resolve_uf(header: Header, override: str | None) -> str | None:
    if override:
        return override.upper()
    if header.state:
        return UF_BY_STATE.get(_ascii(header.state).upper())
    return None


def write_events(path: Path, rows: list[TideRow], station: str, edition: int | None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(EVENT_FIELDS)
        for row in rows:
            writer.writerow(
                [
                    station,
                    f"{row.local:%Y-%m-%d %H:%M}",
                    row.kind,
                    f"{row.height_m:.2f}",
                    edition or "",
                ]
            )


def upsert_station_file(path: Path, row: dict[str, str]) -> None:
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    rows = [r for r in rows if r["id"] != row["id"]] + [row]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATION_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def edition_from_metadata(path: Path) -> int | None:
    import pymupdf

    with pymupdf.open(path) as pdf:
        title = str((pdf.metadata or {}).get("title", ""))
    match = re.search(r"(\d+)\s*ED", title)
    return int(match.group(1)) if match else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Converte PDFs da DHN no CSV padrão de marés.")
    parser.add_argument("pdfs", nargs="+", type=Path)
    parser.add_argument("--stations", type=Path, default=Path("data/tide_stations.csv"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/tides"))
    parser.add_argument(
        "--edition", type=int, help="edição da publicação (padrão: metadados do PDF)"
    )
    parser.add_argument("--uf", help="UF da estação, se o PDF não a informar")
    args = parser.parse_args(argv)

    failed = False
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for pdf in args.pdfs:
        table = parse_pdf(pdf)
        rows = build_rows(table)
        uf = resolve_uf(table.header, args.uf)
        station = station_row(table.header, uf)
        print(f"{pdf.name}: {station['id']} ({station['name']}), {len(rows)} eventos")
        for warning in table.warnings[:10]:
            print(f"  aviso: {warning}")
        if len(table.warnings) > 10:
            print(f"  ... e mais {len(table.warnings) - 10} avisos")
        if table.errors or not uf:
            failed = True
            for error in table.errors[:20]:
                print(f"  ERRO: {error}")
            if not uf:
                print("  ERRO: UF não identificada; use --uf")
            continue
        edition = args.edition or edition_from_metadata(pdf)
        if edition is None:
            print("  aviso: edição não identificada nos metadados; use --edition 63 se for o caso")
        write_events(
            args.out_dir / f"{station['id']}-{table.header.year}.csv", rows, station["id"], edition
        )
        upsert_station_file(args.stations, station)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
