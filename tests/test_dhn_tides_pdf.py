"""Testes do parser dos PDFs da DHN com páginas sintéticas (o layout imita as edições de 2026).
Os PDFs reais podem estar sujeitos a termos de uso (a verificar) e não ficam no repositório:
se DHN_PDF_DIR apontar para uma pasta com eles, o último teste também os confere."""

import calendar
import math
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ocean.ingestion.parsers import dhn_tides_pdf as d
from ocean.ingestion.parsers import tide_csv

YEAR = 2026
MONTH_NAMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]  # fmt: skip
WEEKDAYS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
HEADER = {
    "title": "PORTO DO TESTE (ESTADO DE PERNAMBUCO) - 2026",
    "coords": "Latitude 08° 03'.4 S Longitude 34° 52' W Fuso UTC -03.0 horas",
    "datum": "DHN 16 Componentes Nível Médio 1.28 m Carta 902",
}


def synthetic_year() -> list[tuple[datetime, float]]:
    """Extremos a cada 6h12, alternando baixa-mar e preamar, durante o ano todo."""
    events, moment, n = [], datetime(YEAR, 1, 1, 0, 30), 0
    while moment.year == YEAR:
        high = n % 2 == 1
        events.append(
            (
                moment,
                round(2.0 + 0.2 * math.sin(n / 7), 2)
                if high
                else round(0.4 + 0.1 * math.cos(n / 5), 2),
            )
        )
        moment += timedelta(hours=6, minutes=12)
        n += 1
    return events


def page_words(page: int, events, glue_weekday=False, nautical=False) -> list[dict]:
    words = []

    def fmt(height):
        return f"{height:.2f}".replace(".", ",") if nautical else f"{height:.2f}"

    def add(text, x0, top):
        words.append({"text": text, "x0": x0, "top": top})

    header = dict(HEADER)
    if nautical:  # estilo do Terminal da Ponta do Félix: sem "UTC" e com vírgula decimal
        header["coords"] = header["coords"].replace("UTC -03.0", "+03.0")
        header["datum"] = header["datum"].replace("1.28", "1,28")
    for top, text in zip((55.7, 66.1, 75.8), header.values(), strict=True):
        x = 80.0
        for token in text.split():
            add(token, x, top)
            x += 40
    by_day: dict[tuple[int, int], list] = {}
    for at, height in events:
        by_day.setdefault((at.month, at.day), []).append((at, height))
    for k in range(8):
        start = 47.7 + 63.8 * k
        month = page * 4 + k // 2 + 1
        if k % 2 == 0:
            add(MONTH_NAMES[month - 1], start + 30, 90.1)
        add("HORA", start, 102.2)
        add("ALT(m)", start + 20.6, 102.2)
        days = range(1, 17) if k % 2 == 0 else range(17, calendar.monthrange(YEAR, month)[1] + 1)
        top = 111.2
        for day in days:
            readings = by_day.get((month, day), [])
            for line, (at, height) in enumerate(readings):
                if line == 0:
                    add(f"{day:02d}", start - 15.6, top + 0.5)
                if line == 1:
                    weekday = WEEKDAYS[datetime(YEAR, month, day).weekday()]
                    if glue_weekday:
                        add(f"{weekday}{at:%H%M}", start - 18, top)
                        add(fmt(height), start + 23.6, top)
                        top += 8
                        continue
                    add(weekday, start - 18, top)
                add(f"{at:%H%M}", start + 4.4, top)
                add(fmt(height), start + 23.6, top)
                top += 8
            top += 9
    return words


def parse_year(events, glue_weekday=False, drop=None, nautical=False):
    table_days, errors = [], []
    header = None
    for page in range(3):
        page_events = [e for e in events if page * 4 < e[0].month <= page * 4 + 4 and e != drop]
        header, days, page_errors = d.parse_page(
            page_words(page, page_events, glue_weekday, nautical)
        )
        table_days.extend(days)
        errors.extend(page_errors)
    return d.ParsedTable(header=header, days=table_days, errors=errors)


def test_roundtrip_whole_year_without_issues():
    events = synthetic_year()
    table = parse_year(events)
    rows = d.build_rows(table)
    assert table.errors == [] and table.warnings == []
    assert [(r.local, r.height_m) for r in rows] == events
    assert [r.kind for r in rows[:4]] == ["low", "high", "low", "high"]
    assert table.header.name == "PORTO DO TESTE" and table.header.mean_level_m == 1.28


def test_weekday_glued_to_time_is_handled():
    table = parse_year(synthetic_year(), glue_weekday=True)
    assert table.errors == []
    assert len(d.build_rows(table)) == len(synthetic_year())


def test_nautical_header_and_decimal_comma():
    events = synthetic_year()
    table = parse_year(events, nautical=True)
    rows = d.build_rows(table)
    assert table.errors == [] and table.header.utc_offset_hours == -3.0
    assert table.header.mean_level_m == 1.28
    assert [(r.local, r.height_m) for r in rows] == events


def test_offset_incompatible_with_longitude_is_rejected():
    text = "\n".join(HEADER.values()).replace("UTC -03.0", "UTC +05.0")
    with pytest.raises(ValueError, match="incompatível"):
        d.parse_header(text)


def test_event_missing_in_source_is_a_warning_and_kinds_stay_correct():
    events = synthetic_year()
    missing = events[700]  # um evento qualquer no meio do ano
    table = parse_year(events, drop=missing)
    rows = d.build_rows(table)
    assert table.errors == []
    assert any("seguidos" in w for w in table.warnings)
    expected = {
        at: kind for (at, _), kind in zip(events, ["low", "high"] * len(events), strict=False)
    }
    assert all(expected[r.local] == r.kind for r in rows)


def test_missing_day_is_an_error():
    events = [e for e in synthetic_year() if not (e[0].month == 5 and e[0].day == 10)]
    table = parse_year(events)
    d.build_rows(table)
    assert any("dia ausente: 10/05" in e for e in table.errors)


def test_days_with_five_or_six_extremes_only_warn():
    table = parse_year(synthetic_year())
    day = next(x for x in table.days if (x.month, x.day) == (3, 11))
    day.readings = [("0010", 0.4), ("0300", 0.5), ("0400", 0.45), *day.readings]  # 6 ou 7
    d.build_rows(table)
    assert not any("11/03" in e for e in table.errors)
    assert any("11/03" in w and "leituras" in w for w in table.warnings)


def test_token_count_mismatch_is_an_error():
    words = page_words(0, [e for e in synthetic_year() if e[0].month <= 4])
    words.append({"text": "1234", "x0": 60.0, "top": 400.0})  # horário solto, sem altura
    _, _, errors = d.parse_page(words)
    assert any("diferem" in e or "ilegível" in e for e in errors)


def test_header_and_station_row():
    header = d.parse_header("\n".join(HEADER.values()))
    assert (header.latitude, header.longitude) == (-8.0567, -34.8667)
    assert header.utc_offset_hours == -3.0 and header.chart_number == "902" and header.year == YEAR
    assert d.resolve_uf(header, None) == "PE"
    row = d.station_row(header, "PE")
    assert row["id"] == "teste-pe" and row["name"] == "Porto do Teste"
    assert row["timezone"] == "Etc/GMT+3" and row["chart_number"] == "902"


@pytest.mark.parametrize(
    "offset, zone",
    [(-3.0, "Etc/GMT+3"), (-4.0, "Etc/GMT+4"), (-2.0, "Etc/GMT+2"), (0.0, "Etc/GMT")],
)
def test_utc_zone(offset, zone):
    assert d.utc_zone(offset) == zone


def test_station_id_without_porto_prefix():
    header = d.parse_header(
        "PORTO DE SÃO LUÍS (ESTADO DO MARANHÃO) - 2026\n"
        "Latitude 02° 31'.8 S Longitude 44° 18' W Fuso UTC -03.0 horas\n"
        "DHN 16 Componentes Nível Médio 3.20 m Carta 401"
    )
    assert d.station_id(header, d.resolve_uf(header, None)) == "sao-luis-ma"


def test_csv_output_roundtrips_through_the_loader(tmp_path):
    events = synthetic_year()
    table = parse_year(events)
    rows = d.build_rows(table)
    station = d.station_row(table.header, "PE")
    stations_path = tmp_path / "stations.csv"
    d.upsert_station_file(stations_path, station)
    d.upsert_station_file(stations_path, station)  # idempotente
    d.write_events(tmp_path / "e.csv", rows, station["id"], 63)

    stations = {s.id: s for s in tide_csv.load_stations(stations_path)}
    assert list(stations) == ["teste-pe"]
    loaded = tide_csv.parse_events(tmp_path / "e.csv", stations)
    assert len(loaded) == len(events) and loaded[0].edition == 63
    assert loaded[0].at == datetime(
        YEAR, 1, 1, 3, 30, tzinfo=loaded[0].at.tzinfo
    )  # 00:30 -03 = 03:30 UTC
    assert tide_csv.check_alternation(loaded) == []


@pytest.mark.skipif(not os.environ.get("DHN_PDF_DIR"), reason="DHN_PDF_DIR não definido")
def test_real_pdfs():
    pdfs = sorted(Path(os.environ["DHN_PDF_DIR"]).glob("*.pdf"))
    assert pdfs
    for pdf in pdfs:
        table = d.parse_pdf(pdf)
        rows = d.build_rows(table)
        assert table.errors == [], pdf.name
        assert 1350 <= len(rows) <= 2600, pdf.name  # maré mista tem mais extremos
