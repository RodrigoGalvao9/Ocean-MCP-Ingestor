"""Consulta de defesos no Postgres (somente leitura)."""

from dataclasses import dataclass, field

import psycopg

from ocean.domain.models.fishing import FishingClosure

NATIONAL = "BR"  # área com uf 'BR': a norma vale para todo o litoral


@dataclass
class Coverage:
    """Um defeso e onde ele vale, dentro de uma UF (mais as áreas nacionais)."""

    closure: FishingClosure
    national: bool = False
    state_wide: bool = False
    municipalities: list[str] = field(default_factory=list)


def closures_for_uf(conn: psycopg.Connection, uf: str) -> list[Coverage]:
    rows = conn.execute(
        """
        SELECT c.id, c.species, c.scientific_name, c.region, c.environment, c.prohibition_start,
               c.prohibition_end, c.year, c.fishing_type, c.legal_reference, c.source_url,
               c.source_type, c.last_verified_at, c.notes,
               a.uf AS area_uf, a.ibge_code, a.municipality
        FROM fishing_closures c
        JOIN fishing_closure_areas a ON a.closure_id = c.id
        WHERE c.environment = 'marine' AND a.uf IN (%s, %s)
        ORDER BY c.id
        """,
        (uf, NATIONAL),
    ).fetchall()
    by_id: dict[int, Coverage] = {}
    for row in rows:
        area_uf, ibge, municipality = (
            row.pop("area_uf"),
            row.pop("ibge_code"),
            row.pop("municipality"),
        )
        item = by_id.setdefault(
            row["id"], Coverage(FishingClosure(**{k: v for k, v in row.items() if k != "id"}))
        )
        if area_uf == NATIONAL:
            item.national = True
        elif ibge == "" and not municipality:
            item.state_wide = True
        elif municipality:
            item.municipalities.append(municipality)
    return list(by_id.values())
