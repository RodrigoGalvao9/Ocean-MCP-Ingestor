"""Ferramentas de conhecimento (RAG): explicações, glossário e conceitos marítimos."""

import logging

from ocean.retrieval.vector.retriever import list_topics, search
from ocean.shared.provenance import Freshness, MaritimeDataResponse, Status

log = logging.getLogger(__name__)

SOURCE = "Base de conhecimento Ocean"
LIMITATION = (
    "Conteúdo informativo e introdutório; não substitui publicações, cartas e avisos "
    "oficiais da Marinha do Brasil."
)


def search_maritime_knowledge(query: str, k: int = 4) -> dict:
    """Busca trechos na base de conhecimento marítimo. Use para perguntas conceituais, por
    exemplo: o que é preamar, como ler uma tábua de marés, o que é defeso, o que é a escala
    Beaufort. Não use para dados em tempo real (maré do dia, vento atual)."""
    k = max(1, min(k, 8))
    try:
        results = search(query, k)
    except Exception:
        log.exception("falha na busca de conhecimento")
        return MaritimeDataResponse.unavailable(
            SOURCE,
            "A base de conhecimento está temporariamente indisponível.",
            freshness=Freshness.REFERENCE,
        ).to_tool_result()

    return MaritimeDataResponse(
        status=Status.OK if results else Status.PARTIAL,
        source=SOURCE,
        freshness=Freshness.REFERENCE,
        data={"results": results},
        limitations=[LIMITATION]
        + ([] if results else ["Nenhum trecho relevante foi encontrado para esta pergunta."]),
    ).to_tool_result()


def list_knowledge_topics() -> dict:
    """Lista os tópicos (id e título) da base de conhecimento marítimo."""
    try:
        topics = list_topics()
    except Exception:
        log.exception("falha ao listar tópicos")
        return MaritimeDataResponse.unavailable(
            SOURCE,
            "A base de conhecimento está temporariamente indisponível.",
            freshness=Freshness.REFERENCE,
        ).to_tool_result()

    return MaritimeDataResponse(
        status=Status.OK,
        source=SOURCE,
        freshness=Freshness.REFERENCE,
        data={"topics": topics},
        limitations=[LIMITATION],
    ).to_tool_result()


def register(mcp) -> None:
    """Registra as ferramentas. Os nomes em português são ALIASES temporários, mantidos
    enquanto a API (ALLOWED_TOOLS) ainda usa os nomes antigos."""
    mcp.tool(name="search_maritime_knowledge")(search_maritime_knowledge)
    mcp.tool(name="list_knowledge_topics")(list_knowledge_topics)
    mcp.tool(name="buscar_conhecimento")(search_maritime_knowledge)
    mcp.tool(name="listar_topicos")(list_knowledge_topics)
