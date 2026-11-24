import psycopg
from psycopg.rows import dict_row

from ocean.shared.config import get_settings


def connect(database_url: str | None = None) -> psycopg.Connection:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL não definido")
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)


def connect_readonly(database_url: str | None = None) -> psycopg.Connection:
    """Conexão para o servidor MCP: toda transação é READ ONLY.

    Vale mesmo que DATABASE_URL aponte para um usuário com permissão de escrita (ex.: o dono do
    banco). Usa `conn.read_only` (BEGIN READ ONLY) e não o parâmetro de startup `options`, que o
    pooler do Neon (pgbouncer) não aceita. O ideal continua sendo um usuário só com SELECT.
    """
    conn = connect(database_url)
    conn.read_only = True
    return conn
