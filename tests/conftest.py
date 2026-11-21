import pytest

from ocean.shared.config import get_settings


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch):
    for var in (
        "ENVIRONMENT", "MCP_AUTH_TOKEN", "DATABASE_URL", "REDIS_URL", "QDRANT_URL",
        "QDRANT_API_KEY", "QDRANT_COLLECTION", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN",
    ):  # fmt: skip
        monkeypatch.delenv(var, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
