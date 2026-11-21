"""Escala Beaufort a partir da velocidade do vento em nós.

Limites inferiores de cada força (WMO), em nós. Os NOMES em português abaixo devem ser
conferidos com a nomenclatura oficial (Marinha/DHN) antes de ir para produção.
"""

from dataclasses import dataclass

# Força N começa em _LOWER_BOUNDS[N]. Força 0: abaixo de 1 nó.
_LOWER_BOUNDS = [0, 1, 4, 7, 11, 17, 22, 28, 34, 41, 48, 56, 64]

_NAMES_PT = [
    "Calmaria",
    "Aragem",
    "Brisa leve",
    "Brisa fraca",
    "Brisa moderada",
    "Brisa forte",
    "Vento fresco",
    "Vento forte",
    "Ventania",
    "Ventania forte",
    "Tempestade",
    "Tempestade violenta",
    "Furacão",
]


@dataclass(frozen=True)
class Beaufort:
    force: int
    name_pt: str


def beaufort_from_knots(knots: float) -> Beaufort:
    if knots < 0:
        raise ValueError("velocidade do vento não pode ser negativa")
    force = max(i for i, lower in enumerate(_LOWER_BOUNDS) if knots >= lower)
    return Beaufort(force=force, name_pt=_NAMES_PT[force])
