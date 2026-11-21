# Ocean MCP + Ingestor

Servidor MCP **somente leitura** e ingestão de dados marítimos brasileiros (condições do mar,
marés, defeso, embarcações, onde vender pescado e base de conhecimento). Alimenta o agente
[`ocean-agent-api`](https://github.com/RodrigoGalvao9/ocean-agent-api).

Um repositório, dois pontos de entrada:

| Ponto de entrada | Comando | Onde roda |
|---|---|---|
| Servidor MCP | `python -m ocean.server` | Render (web service, plano free) |
| Ingestão | `python -m ocean.ingestion.run <job>` | GitHub Actions |

## Regras do projeto

1. O servidor é **somente leitura**: nenhuma ferramenta escreve estado.
2. O caminho da requisição lê Postgres, Qdrant e cache. Só as ferramentas "ao vivo" (clima, GFW) chamam fonte externa, com timeout, nova tentativa limitada e fallback para cache marcado `stale`.
3. Toda ferramenta devolve `MaritimeDataResponse` (`src/ocean/shared/provenance.py`): fonte, data de consulta, momento a que o dado se refere, limitações.
4. Interpretação (Beaufort, fase da maré) é código determinístico em `domain/services`, com testes. O LLM só explica o resultado.
5. `server` e `ingestion` **nunca importam um do outro** (verificado por `lint-imports` no CI). `domain` não depende de nada do projeto.
6. Uso **não comercial** (GFW e Open-Meteo exigem).

## Estrutura

```
src/ocean/
  server/       MCP: ferramentas, autenticação, /health
  ingestion/    jobs, parsers, coletores
  domain/       modelos e serviços de interpretação
  retrieval/    vector (Qdrant) e structured (Postgres)
  storage/      postgres (conexão, migrações, execuções), cache (Redis)
  shared/       config, logging, http, proveniência
migrations/     SQL do esquema (a ingestão é a dona do esquema)
content/knowledge/   documentos do RAG (Markdown com cabeçalho)
data/           tabelas curadas (CSV)
tests/
```

## Primeiros passos

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -e ".[server,ingest,dev]"
copy .env.example .env             # preencha QDRANT_*, CLOUDFLARE_* (e DATABASE_URL quando existir)

pytest -q                          # testes
ruff check .                       # lint
lint-imports                       # regras de importação
```

Python **3.12** em todo lugar (imagem, GitHub Actions e desenvolvimento). Depois da primeira instalação
bem-sucedida, fixe as versões: `pip freeze > constraints.txt`.

### Rodar o servidor local

```bash
python -m ocean.server             # http://localhost:8000  (/health, MCP em /mcp)
```

### Indexar a base de conhecimento

```bash
python -m ocean.ingestion.run knowledge_refresh
python -m ocean.retrieval.vector.retriever "O que é preamar?"
```

Os arquivos de `content/knowledge/*.md` vêm marcados `revisado: nao`: são rascunhos a revisar com fonte oficial.
A coleção padrão é `ocean_conhecimento` (não mexe na coleção antiga `conhecimento_maritimo`).

### Banco de dados (fase 2 em diante)

```bash
python -m ocean.storage.postgres.migrate      # aplica migrations/*.sql
python -m ocean.ingestion.run ping            # confere a conexão e registra uma execução
```

## Ferramentas MCP

| Ferramenta | Situação |
|---|---|
| `search_maritime_knowledge`, `list_knowledge_topics` | implementadas (aliases temporários: `buscar_conhecimento`, `listar_topicos`) |
| `get_tide_table`, `get_marine_conditions` | fase 2 |
| `get_fishing_closures` | fase 3 |
| `search_vessels` | fase 4 |
| `find_fish_markets` | fase 5 |

## Deploy

**Servidor (Render):** *New → Blueprint* apontando para este repositório (`render.yaml`). Preencha as variáveis
marcadas `sync: false`. `MCP_AUTH_TOKEN` deve ser **igual** ao da API. Na API, atualize `ALLOWED_TOOLS`
(variável no painel do Render) e `MCP_SERVER_URL`.

**Ingestão (GitHub Actions):** em *Settings → Secrets and variables → Actions*, crie
`DATABASE_URL_ADMIN`, `QDRANT_URL`, `QDRANT_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, `CLOUDFLARE_API_TOKEN`.
Rode *Actions → Ingestão → Run workflow* e escolha o job.

## Documentação

Visão do projeto e guia técnico (decisões, contrato, plano por fases): documentos "Ocean — Visão do Projeto"
e "Ocean — Guia Técnico".
