"""Regras de calendário do defeso (puras, sem banco)."""

from datetime import date

from ocean.domain.models.fishing import FishingClosure


def _md(value: str) -> tuple[int, int]:
    month, day = value.split("-")
    return int(month), int(day)


def _safe_date(year: int, month: int, day: int) -> date:
    """29/02 em ano não bissexto vira 28/02 (as portarias usam 28/02 como fim de fevereiro)."""
    try:
        return date(year, month, day)
    except ValueError:
        return date(year, month, day - 1)


def windows(closure: FishingClosure, year: int) -> list[tuple[date, date]]:
    """Períodos (início, fim) que COMEÇAM em `year`.

    Para defeso anual, devolve um período; para defeso de um ano específico, devolve o período
    só se `year` for esse ano. O fim cai no ano seguinte quando atravessa a virada.
    """
    if closure.year is not None and closure.year != year:
        return []
    sm, sd = _md(closure.prohibition_start)
    em, ed = _md(closure.prohibition_end)
    start = _safe_date(year, sm, sd)
    end_year = year if (em, ed) >= (sm, sd) else year + 1
    return [(start, _safe_date(end_year, em, ed))]


def in_force(closure: FishingClosure, day: date) -> bool:
    """O defeso vale em `day`? Considera períodos que começaram no ano anterior."""
    for year in (day.year - 1, day.year):
        for start, end in windows(closure, year):
            if start <= day <= end:
                return True
    return False


def next_window(closure: FishingClosure, day: date) -> tuple[date, date] | None:
    """Próximo período que ainda não começou depois de `day` (até 3 anos à frente)."""
    upcoming = [
        w for year in range(day.year, day.year + 4) for w in windows(closure, year) if w[0] > day
    ]
    return min(upcoming) if upcoming else None
