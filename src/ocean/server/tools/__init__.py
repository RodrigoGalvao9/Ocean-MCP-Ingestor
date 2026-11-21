"""Cada módulo expõe `register(mcp)`. Para criar uma ferramenta nova: função simples com
parâmetros de tipo simples (str, int, float, bool), docstring em português com exemplos de uso
(é por ela que o modelo escolhe a ferramenta), retorno `MaritimeDataResponse.to_tool_result()`."""

from ocean.server.tools import knowledge


def register_all(mcp) -> None:
    knowledge.register(mcp)
