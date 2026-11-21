import pytest

pytest.importorskip("fastmcp")

from ocean.server.app import create_server  # noqa: E402
from ocean.shared.config import Settings  # noqa: E402


def test_production_requires_token():
    with pytest.raises(RuntimeError):
        create_server(Settings(_env_file=None, environment="production"))


def test_server_builds_without_token_in_development():
    assert create_server(Settings(_env_file=None, environment="development")) is not None
