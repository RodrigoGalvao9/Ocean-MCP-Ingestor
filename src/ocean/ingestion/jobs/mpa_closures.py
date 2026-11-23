"""Carrega os defesos (fase 3) de data/defeso/*.csv no Postgres. Idempotente e de carga completa.

Arquivos (só na máquina de quem carrega; nada de data/ vai ao Git):
- defeso_closures.csv + defeso_areas.csv: saída de ocean.ingestion.parsers.defeso_municipal.
- curated_closures.csv + curated_areas.csv: defesos curados à mão a partir das normas (vencem a
  tabela quando coincidem).
Basta existir um dos pares. Ver docs/defeso.md.
"""

import logging

from ocean.ingestion.jobs.base import JobResult
from ocean.ingestion.parsers import defeso_csv
from ocean.shared.config import Settings
from ocean.storage.postgres import closures
from ocean.storage.postgres.db import connect

log = logging.getLogger(__name__)
PAIRS = (("defeso_closures.csv", "defeso_areas.csv"), ("curated_closures.csv", "curated_areas.csv"))


def run(settings: Settings) -> JobResult:
    folder = settings.data_dir / "defeso"
    groups = []
    for closures_name, areas_name in PAIRS:
        closures_path, areas_path = folder / closures_name, folder / areas_name
        if not closures_path.exists():
            continue
        if not areas_path.exists():
            raise FileNotFoundError(f"{areas_path} não existe (par de {closures_name}).")
        loaded = defeso_csv.load_pair(closures_path, areas_path)
        log.info("defesos lidos", extra={"file": closures_name, "closures": len(loaded)})
        groups.append(loaded)
    if not groups:
        raise FileNotFoundError(
            f"nenhum CSV de defeso em {folder}. Gere com "
            "'python -m ocean.ingestion.parsers.defeso_municipal <tabela.txt>' "
            "(ver docs/defeso.md)."
        )
    items = defeso_csv.merge(groups)
    with connect(settings.database_url) as conn:
        n_closures, n_areas = closures.replace_all(conn, items)
    log.info("defesos gravados", extra={"closures": n_closures, "areas": n_areas})
    return JobResult(rows=n_closures + n_areas, source_version="MPA/IBAMA (ver last_verified_at)")
