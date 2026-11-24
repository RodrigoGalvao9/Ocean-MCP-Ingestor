"""O servidor MCP nunca escreve: as ferramentas abrem conexão READ ONLY."""

from ocean.server.tools import fishing_closures, tide_table
from ocean.storage.postgres import db


class _FakeConn:
    read_only = False


def test_connect_readonly_marks_the_connection_read_only(monkeypatch):
    monkeypatch.setattr(db, "connect", lambda url=None: _FakeConn())
    assert db.connect_readonly("postgresql://x").read_only is True


def test_server_tools_use_the_read_only_connection():
    assert fishing_closures.connect is db.connect_readonly
    assert tide_table.connect is db.connect_readonly
