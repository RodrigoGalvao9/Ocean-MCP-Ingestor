"""Configuração única do projeto (variáveis de ambiente e .env)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/ocean/shared/config.py -> parents: shared, ocean, src, raiz do repositório
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # env_ignore_empty: `QDRANT_API_KEY=` vazio no .env vale como "não definido",
    # em vez de sobrescrever o padrão com texto vazio (bug que já aconteceu no Langfuse).
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    environment: str = "development"
    log_level: str = "INFO"

    # Servidor MCP
    mcp_host: str = "0.0.0.0"
    port: int = 8000
    mcp_auth_token: str | None = None

    # Armazenamento
    database_url: str | None = None
    redis_url: str | None = None

    # Qdrant + embeddings
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "ocean_conhecimento"
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    embedding_model: str = "@cf/google/embeddinggemma-2"
    embedding_dim: int = 512
    fastembed_cache_dir: str | None = None

    # Fontes externas
    gfw_token: str | None = None

    # Caminhos (só fazem sentido no repositório, não na imagem do servidor)
    migrations_dir: Path = REPO_ROOT / "migrations"
    knowledge_dir: Path = REPO_ROOT / "content" / "knowledge"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def cloudflare_embedding_url(self) -> str | None:
        if not self.cloudflare_account_id:
            return None
        return (
            "https://api.cloudflare.com/client/v4/accounts/"
            f"{self.cloudflare_account_id}/ai/run/{self.embedding_model}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
