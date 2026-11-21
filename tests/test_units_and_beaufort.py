import pytest

from ocean.domain.services.beaufort import beaufort_from_knots
from ocean.domain.services.units import (
    degrees_to_compass,
    kmh_to_knots,
    knots_to_kmh,
    ms_to_knots,
)


def test_conversions():
    assert ms_to_knots(1) == pytest.approx(1.9438, abs=1e-3)
    assert knots_to_kmh(1) == pytest.approx(1.852)
    assert kmh_to_knots(1.852) == pytest.approx(1.0)


@pytest.mark.parametrize(
    ("degrees", "expected"),
    [(0, "N"), (90, "L"), (180, "S"), (270, "O"), (45, "NE"), (225, "SO"), (359, "N"), (360, "N")],
)
def test_compass(degrees, expected):
    assert degrees_to_compass(degrees) == expected


@pytest.mark.parametrize(
    ("knots", "force"),
    [(0, 0), (0.9, 0), (1, 1), (3.9, 1), (4, 2), (10.5, 3), (16.9, 4), (17, 5), (27, 6),
     (33.9, 7), (34, 8), (47, 9), (55, 10), (63.9, 11), (64, 12), (120, 12)],
)  # fmt: skip
def test_beaufort_forces(knots, force):
    assert beaufort_from_knots(knots).force == force


def test_beaufort_negative_rejected():
    with pytest.raises(ValueError):
        beaufort_from_knots(-1)
