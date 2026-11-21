from ocean.shared.config import Settings


def test_empty_env_vars_are_ignored(monkeypatch):
    monkeypatch.setenv("QDRANT_API_KEY", "")
    monkeypatch.setenv("QDRANT_COLLECTION", "")
    s = Settings(_env_file=None)
    assert s.qdrant_api_key is None
    assert s.qdrant_collection == "ocean_conhecimento"


def test_cloudflare_url_needs_account_id(monkeypatch):
    assert Settings(_env_file=None).cloudflare_embedding_url is None
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "abc")
    assert "accounts/abc/ai/run/" in Settings(_env_file=None).cloudflare_embedding_url


def test_is_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "Production")
    assert Settings(_env_file=None).is_production
