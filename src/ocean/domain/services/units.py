"""Conversões de unidades e direção do vento."""

KNOT_IN_KMH = 1.852
MS_TO_KNOTS = 3600 / 1852  # 1 m/s = 1,9438 nós

# Pontos cardeais em português: L = Leste, O = Oeste.
_COMPASS_PT = [
    "N", "NNE", "NE", "ENE", "L", "ESE", "SE", "SSE",
    "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO",
]  # fmt: skip


def ms_to_knots(value: float) -> float:
    return value * MS_TO_KNOTS


def kmh_to_knots(value: float) -> float:
    return value / KNOT_IN_KMH


def knots_to_kmh(value: float) -> float:
    return value * KNOT_IN_KMH


def degrees_to_compass(degrees: float) -> str:
    """Direção de onde o vento SOPRA (convenção meteorológica), em pontos cardeais."""
    index = int((degrees % 360) / 22.5 + 0.5) % 16
    return _COMPASS_PT[index]
