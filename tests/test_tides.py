from datetime import UTC, datetime

from ocean.domain.models.tide import TideEvent
from ocean.domain.services.tides import tide_state


def ev(hour, kind, h=1.0):
    at = datetime(2026, 1, 1, hour, tzinfo=UTC)
    return TideEvent(station_id="x", at=at, kind=kind, height_m=h)


EVENTS = [ev(0, "low", 0.1), ev(6, "high", 1.5), ev(12, "low", 0.2), ev(18, "high", 1.4)]


def test_rising_between_low_and_high():
    s = tide_state(datetime(2026, 1, 1, 3, tzinfo=UTC), EVENTS)
    assert s.phase == "rising" and s.phase_pt == "enchente"
    assert s.next_high.at.hour == 6 and s.next_low.at.hour == 12


def test_falling_between_high_and_low():
    s = tide_state(datetime(2026, 1, 1, 8, tzinfo=UTC), EVENTS)
    assert s.phase == "falling" and s.phase_pt == "vazante"
    assert s.previous.at.hour == 6


def test_unknown_when_no_future_events():
    s = tide_state(datetime(2026, 1, 2, 0, tzinfo=UTC), EVENTS)
    assert s.phase == "unknown" and s.next_high is None


def test_unknown_when_data_missing_between_same_kinds():
    events = [ev(0, "high"), ev(12, "high")]
    assert tide_state(datetime(2026, 1, 1, 6, tzinfo=UTC), events).phase == "unknown"
