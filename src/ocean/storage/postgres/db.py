import psycopg
from psycopg.rows import dict_row

from ocean.shared.config import get_settings


def connect(database_url: str | None = None) -> psycopg.Connection:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)
