"""Ponto de entrada do servidor: python -m ocean.server"""

import logging
import threading

from ocean.server.app import create_server
from ocean.shared.config import get_settings
from ocean.shared.logging import configure_logging

log = logging.getLogger("ocean.server")


def _warm_up() -> None:
    try:
        from ocean.retrieval.vector.embeddings import embed_sparse

        embed_sparse(["aquecimento"])
        log.info("BM25 carregado")
    except Exception:
        log.exception("não foi possível carregar o BM25; a 1ª busca pode demorar ou falhar")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    # Aquece o BM25 local em segundo plano: o servidor já responde (/health) enquanto o modelo
    # carrega, o que ajuda na partida a frio. O embedding denso é gerado pela Cloudflare.
    threading.Thread(target=_warm_up, name="warm-up", daemon=True).start()

    server = create_server(settings)
    server.run(transport="http", host=settings.mcp_host, port=settings.port)


if __name__ == "__main__":
    main()
