"""Escrita de defesos e áreas (usada só pela ingestão, com usuário admin)."""

import psycopg

from ocean.domain.models.fishing import LoadedClosure

_CLOSURE_SQL = """
INSERT INTO fishing_closures (species, scientific_name, region, environment, prohibition_start,
    prohibition_end, year, fishing_type, legal_reference, source_url, source_type,
    last_verified_at, notes)
VALUES (%(species)s, %(scientific_name)s, %(region)s, %(environment)s, %(prohibition_start)s,
    %(prohibition_end)s, %(year)s, %(fishing_type)s, %(legal_reference)s, %(source_url)s,
    %(source_type)s, %(last_verified_at)s, %(notes)s)
ON CONFLICT (legal_reference, species, prohibition_start, prohibition_end, COALESCE(year, 0))
DO UPDATE SET scientific_name = EXCLUDED.scientific_name, region = EXCLUDED.region,
    environment = EXCLUDED.environment, fishing_type = EXCLUDED.fishing_type,
    source_url = EXCLUDED.source_url, source_type = EXCLUDED.source_type,
    last_verified_at = EXCLUDED.last_verified_at, notes = EXCLUDED.notes, ingested_at = now()
RETURNING id
"""

_AREA_SQL = (
    "INSERT INTO fishing_closure_areas (closure_id, uf, ibge_code, municipality)"
    " VALUES (%s, %s, %s, %s)"
)


def replace_all(conn: psycopg.Connection, items: list[LoadedClosure]) -> tuple[int, int]:
    """Carga completa e idempotente, numa transação: grava os defesos e suas áreas e remove o
    que não está mais na carga (a tabela só é populada por este job). Devolve (defesos, áreas)."""
    if not items:
        raise ValueError("carga vazia: nada seria gravado (recusando apagar a tabela)")
    n_areas = 0
    with conn.transaction(), conn.cursor() as cur:
        ids: list[int] = []
        for item in items:
            row = cur.execute(_CLOSURE_SQL, item.closure.model_dump()).fetchone()
            closure_id = row["id"]
            ids.append(closure_id)
            cur.execute("DELETE FROM fishing_closure_areas WHERE closure_id = %s", (closure_id,))
            params = [(closure_id, uf, ibge, name) for (uf, ibge), name in item.areas.items()]
            cur.executemany(_AREA_SQL, params)
            n_areas += len(params)
        cur.execute("DELETE FROM fishing_closures WHERE id <> ALL(%s)", (ids,))
    return len(items), n_areas
