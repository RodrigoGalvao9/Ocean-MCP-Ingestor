from datetime import UTC, datetime
from pathlib import Path

import pytest

from ocean.domain.models.tide import TideEvent, TideStation
from ocean.ingestion.parsers import tide_csv

REPO_DATA = Path(__file__).resolve().parents[1] / "data"

STATIONS = {
    "natal-rn": TideStation(
        id="natal-rn",
        name="Natal",
        uf="RN",
        latitude=-5.78,
        longitude=-35.21,
        timezone="America/Fortaleza",
    ),  # fmt: skip
    "noronha-pe": TideStation(
        id="noronha-pe",
        name="Noronha",
        uf="PE",
        latitude=-3.85,
        longitude=-32.42,
        timezone="America/Noronha",
    ),  # fmt: skip
}
HEADER = "station_id,local_datetime,kind,height_m,edition\n"


def _write(tmp_path, body: str) -> Path:
    path = tmp_path / "t.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_converts_local_time_to_utc(tmp_path):
    path = _write(
        tmp_path, "natal-rn,2026-01-01 06:12,low,0.35,63\nnoronha-pe,2026-01-01 06:12,high,2.1,\n"
    )
    natal, noronha = tide_csv.parse_events(path, STATIONS)
    assert natal.at == datetime(2026, 1, 1, 9, 12, tzinfo=UTC)  # UTC-3
    assert noronha.at == datetime(2026, 1, 1, 8, 12, tzinfo=UTC)  # UTC-2
    assert natal.edition == 63 and noronha.edition is None and natal.kind == "low"


@pytest.mark.parametrize(
    "row, fragment",
    [
        ("recife,2026-01-01 06:12,low,0.3,", "estação desconhecida"),
        ("natal-rn,2026-01-01 06:12,alta,0.3,", "kind"),
        ("natal-rn,2026-01-01 06:12,low,abc,", "t.csv:2"),
        ("natal-rn,01/01/2026 06:12,low,0.3,", "t.csv:2"),
        ("natal-rn,2026-01-01 06:12,low,15.0,", "fora de"),
        ("natal-rn,2026-01-01T06:12-03:00,low,0.3,", "sem fuso"),
    ],
)
def test_invalid_rows_name_file_and_line(tmp_path, row, fragment):
    with pytest.raises(tide_csv.TideDataError, match=fragment):
        tide_csv.parse_events(_write(tmp_path, row + "\n"), STATIONS)


def test_alternation_warning():
    def event(hour, kind):
        return TideEvent(
            station_id="a", at=datetime(2026, 1, 1, hour, tzinfo=UTC), kind=kind, height_m=1
        )

    assert tide_csv.check_alternation([event(1, "low"), event(7, "high"), event(13, "low")]) == []
    warnings = tide_csv.check_alternation([event(1, "low"), event(7, "high"), event(13, "high")])
    assert len(warnings) == 1 and "high" in warnings[0]


def test_repo_station_file_is_valid():
    stations = tide_csv.load_stations(REPO_DATA / "tide_stations.csv")
    assert {s.id for s in stations} >= {"natal-rn", "itaqui-ma"}
    assert all(-35 < s.latitude < 6 for s in stations)


def test_duplicate_station_ids_rejected(tmp_path):
    path = tmp_path / "s.csv"
    path.write_text(
        "id,name,uf,latitude,longitude,chart_number,timezone,datum_note\n"
        "a,A,RN,-5,-35,,America/Fortaleza,\na,B,RN,-5,-35,,America/Fortaleza,\n",
        encoding="utf-8",
    )
    with pytest.raises(tide_csv.TideDataError, match="repetidos"):
        tide_csv.load_stations(path)
