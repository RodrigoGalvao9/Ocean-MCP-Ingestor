from datetime import date

from ocean.domain.models.fishing import FishingClosure
from ocean.domain.services import closures


def _c(start, end, year=None):
    return FishingClosure(
        species="Lagosta vermelha",
        prohibition_start=start,
        prohibition_end=end,
        year=year,
        legal_reference="Portaria SAP/MAPA nº 221/2021",
    )


def test_defaults_match_expected_json_shape():
    c = _c("11-01", "04-30")
    assert c.environment == "marine" and c.source_type == "official" and c.year is None


def test_annual_window_inside_one_year():
    c = _c("08-01", "09-30")
    assert closures.windows(c, 2026) == [(date(2026, 8, 1), date(2026, 9, 30))]
    assert closures.in_force(c, date(2026, 8, 1)) and closures.in_force(c, date(2026, 9, 30))
    assert not closures.in_force(c, date(2026, 7, 31)) and not closures.in_force(
        c, date(2026, 10, 1)
    )


def test_window_crossing_new_year():
    c = _c("11-01", "04-30")
    assert closures.windows(c, 2026) == [(date(2026, 11, 1), date(2027, 4, 30))]
    assert closures.in_force(c, date(2026, 12, 25))
    assert closures.in_force(c, date(2027, 4, 30))  # começou em 2026
    assert closures.in_force(c, date(2026, 2, 10))  # começou em 2025
    assert not closures.in_force(c, date(2026, 5, 1))
    assert not closures.in_force(c, date(2026, 10, 31))


def test_february_28_end_covers_leap_and_common_years():
    c = _c("11-01", "02-29")
    assert closures.windows(c, 2026)[0][1] == date(2027, 2, 28)
    assert closures.windows(c, 2027)[0][1] == date(2028, 2, 29)


def test_year_specific_window():
    c = _c("01-18", "01-23", year=2026)
    assert closures.in_force(c, date(2026, 1, 20))
    assert not closures.in_force(c, date(2027, 1, 20))
    assert closures.windows(c, 2027) == []


def test_next_window():
    c = _c("11-01", "04-30")
    assert closures.next_window(c, date(2026, 5, 10)) == (date(2026, 11, 1), date(2027, 4, 30))
    assert closures.next_window(c, date(2026, 12, 1)) == (date(2027, 11, 1), date(2028, 4, 30))
    assert closures.next_window(_c("01-18", "01-23", year=2026), date(2026, 6, 1)) is None
