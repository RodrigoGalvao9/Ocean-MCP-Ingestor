# Arquitetura

## Limites dos módulos

```text
server     -> domain, retrieval, storage, shared
ingestion  -> domain, retrieval, storage, shared
domain     -> somente regras e modelos próprios
```

`server` e `ingestion` não podem importar um ao outro. `domain` permanece independente de
infraestrutura para que regras como escala Beaufort, distância geográfica e fase da maré sejam
determinísticas e testáveis.

## Fluxo de consulta

1. O cliente envia uma chamada MCP para `/mcp`.
2. A ferramenta valida o nome do lugar e os parâmetros.
3. O servidor consulta cache, banco, Qdrant ou uma fonte ao vivo conforme a ferramenta.
4. A resposta é normalizada em `MaritimeDataResponse`.
5. O consumidor recebe dados, fonte, timestamp, atualidade e limitações.

## Fluxo de ingestão

1. Um job lê PDFs, CSVs ou documentos Markdown.
2. Parsers validam e normalizam os dados.
3. PostgreSQL recebe dados estruturados e Qdrant recebe documentos indexáveis.
4. O servidor consulta esses armazenamentos sem executar a ingestão.

## Armazenamentos

| Armazenamento | Responsabilidade |
|---|---|
| PostgreSQL | Estações, eventos de maré e dados estruturados |
| Qdrant | Busca vetorial da base de conhecimento |
| Redis | Cache de dados ao vivo e fallback stale |

## Proveniência

Toda ferramenta deve devolver a fonte consultada, o momento de recuperação, o timestamp do
dado quando existir e limitações que possam afetar a interpretação. Fallbacks antigos devem ser
marcados como `stale`, nunca apresentados como dados atuais.
