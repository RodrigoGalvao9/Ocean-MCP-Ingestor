"""Servidor MCP (somente leitura)."""

import logging

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from ocean.server.tools import register_all
from ocean.shared.config import Settings, get_settings

log = logging.getLogger(__name__)


def _memory_mb() -> int | None:
    """Memória residente do processo em MB (só Linux)."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024)
    except OSError:
        pass
    return None


def _create_auth(settings: Settings):
    """Autenticação Bearer. Em production o servidor não sobe sem MCP_AUTH_TOKEN."""
    token = (settings.mcp_auth_token or "").strip()
    if not token:
        if settings.is_production:
            raise RuntimeError("MCP_AUTH_TOKEN é obrigatório quando ENVIRONMENT=production")
        log.warning("MCP_AUTH_TOKEN não definido: servidor SEM autenticação (uso local)")
        return None

    try:
        from fastmcp.server.auth.providers.jwt import StaticTokenVerifier
    except ImportError:  # caminho em versões mais novas do FastMCP
        from fastmcp.server.auth.verifiers import StaticTokenVerifier

    return StaticTokenVerifier(tokens={token: {"client_id": "ocean-agent-api", "scopes": []}})


def create_server(settings: Settings | None = None) -> FastMCP:
    settings = settings or get_settings()
    mcp = FastMCP("ocean-maritime", auth=_create_auth(settings))

    @mcp.custom_route("/health", methods=["GET"])
    async def health(request: Request) -> JSONResponse:
        """Verificação de saúde (pública, sem dados sensíveis)."""
        return JSONResponse({"status": "ok", "memoria_mb": _memory_mb()})

    register_all(mcp)
    return mcp
