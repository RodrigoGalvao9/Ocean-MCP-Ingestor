"""Interpretação determinística de vento e ondas (sem alertas: não há limiar citável).

Os limites de alerta (vento, onda) só entram aqui quando houver fonte oficial citável.
Até lá, o serviço apenas converte unidades e classifica o vento na escala Beaufort.
"""

from typing import Any

from ocean.domain.services.beaufort import beaufort_from_knots
from ocean.domain.services.units import degrees_to_compass, knots_to_kmh, ms_to_knots


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(value, digits)


def wind_summary(
    speed_ms: float | None, direction_deg: float | None, gust_ms: float | None
) -> dict[str, Any] | None:
    """Vento em nós e km/h, direção de onde sopra e força Beaufort. None se não há velocidade."""
    if speed_ms is None:
        return None
    knots = ms_to_knots(speed_ms)
    force = beaufort_from_knots(knots)
    gust_knots = None if gust_ms is None else ms_to_knots(gust_ms)
    return {
        "speed_knots": _round(knots),
        "speed_kmh": _round(knots_to_kmh(knots)),
        "direction_deg": None if direction_deg is None else round(direction_deg),
        "direction_from": None if direction_deg is None else degrees_to_compass(direction_deg),
        "gusts_knots": _round(gust_knots),
        "gusts_kmh": None if gust_knots is None else _round(knots_to_kmh(gust_knots)),
        "beaufort_force": force.force,
        "beaufort_name": force.name_pt,
    }


def wave_summary(
    height_m: float | None, period_s: float | None, direction_deg: float | None
) -> dict[str, Any] | None:
    """Ondas. A direção fica em graus, como entregue pelo modelo (sem conversão a pontos
    cardeais, para não afirmar uma convenção não verificada)."""
    if height_m is None and period_s is None:
        return None
    return {
        "height_m": _round(height_m, 2),
        "period_s": _round(period_s),
        "direction_deg": None if direction_deg is None else round(direction_deg),
    }
