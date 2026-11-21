# Ocean MCP + Ingestor

Servidor MCP **somente leitura** e ingestão de dados marítimos brasileiros (condições do mar,
marés, defeso, embarcações, onde vender pescado e base de conhecimento). Alimenta o agente
[`ocean-agent-api`](https://github.com/RodrigoGalvao9/ocean-agent-api).

O projeto está dividido entre execução local, ingestão automática e hospedagem em nuvem.
Qualquer pessoa pode usar o servidor como desenvolvedor, contanto que respeite as fontes,
os créditos dos serviços externos e as regras de uso não comercial das APIs.

| Componente | Comando | Hospedagem recomendada |
|---|---|---|
| Servidor MCP | `python -m ocean.server` | Render |
| Ingestão | `python -m ocean.ingestion.run <job>` | GitHub Actions |
| Banco PostgreSQL | migrations em `migrations/` | Neon ou Supabase |
| Busca vetorial | coleção configurada no Qdrant | Qdrant Cloud |
| Cache | Redis | Render Key Value ou Redis compatível |

## Uso público

O projeto oferece ferramentas MCP de consulta. Ele não altera o estado das fontes externas
e não expõe operações de escrita para seus consumidores.

O `MCP_AUTH_TOKEN` protege o servidor em produção. Quem consumir o MCP precisa enviar o mesmo
Bearer token usado pela API `ocean-agent-api`. O `/health` continua público e serve apenas para
confirmar que o processo está operacional.

## Regras do projeto

1. O servidor é **somente leitura**: nenhuma ferramenta escreve estado.
2. O caminho de requisição lê Postgres, Qdrant e cache. Somente fontes ao vivo podem acessar
   serviços externos, usando timeout, novas tentativas limitadas e fallback para cache marcado
   como `stale`.
3. Toda ferramenta devolve `MaritimeDataResponse` (`src/ocean/shared/provenance.py`), com fonte,
   data da consulta, momento do dado e limitações.
4. Interpretação determinística, como escala Beaufort e fase da maré, fica em `domain/services`.
   O modelo de linguagem explica o resultado, mas não calcula a regra.
5. `server` e `ingestion` nunca importam um ao outro. Esse limite arquitetural é verificado
   pelo `lint-imports` no CI.
6. GFW e Open-Meteo exigem uso não comercial. Verifique os termos das fontes antes de ampliar
   o projeto ou de oferecer o serviço a terceiros.

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
.\.venv\Scripts\Activate.ps1     # Windows PowerShell
# source .venv/bin/activate      # Linux/macOS
pip install -e ".[server,ingest,dev]"
Copy-Item .env.example .env       # Windows
# cp .env.example .env           # Linux/macOS
```

Edite o `.env` com as credenciais próprias. Nunca faça commit desse arquivo.
Use os nomes da seção "Variáveis de ambiente" abaixo.

```bash
pytest -q
ruff check .
lint-imports
```

Use Python **3.12** no desenvolvimento, na imagem Docker e no GitHub Actions.
Depois da primeira instalação bem-sucedida, fixe o ambiente com
`pip freeze > constraints.txt`.

## Variáveis de ambiente

Crie valores próprios em cada provedor. Não reutilize credenciais do repositório.

| Variável | Uso |
|---|---|
| `MCP_AUTH_TOKEN` | Protege o servidor MCP em produção |
| `DATABASE_URL` | Banco PostgreSQL acessado localmente ou pelo servidor |
| `DATABASE_URL_UNPOOLED` | URL direta do Neon, quando fornecida pelo provedor |
| `REDIS_URL` | Cache Redis |
| `QDRANT_URL` | Endpoint da instância Qdrant |
| `QDRANT_API_KEY` | Chave da instância Qdrant |
| `QDRANT_COLLECTION` | Coleção padrão, por exemplo `ocean_conhecimento` |
| `CLOUDFLARE_ACCOUNT_ID` | Conta usada para embeddings |
| `CLOUDFLARE_API_TOKEN` | Token Cloudflare com acesso ao modelo |

### Variáveis reservadas à ingestão

No GitHub Actions, configure estes secrets em
**Settings → Secrets and variables → Actions**:

- `DATABASE_URL_ADMIN`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

`DATABASE_URL_ADMIN` é a URL de um usuário administrativo do PostgreSQL. Ela é usada somente
pelo workflow de ingestão e pelas migrations. O servidor público deve usar preferencialmente
`DATABASE_URL` associado a um usuário somente leitura.

### Rodar o servidor local

```bash
python -m ocean.server             # http://localhost:8000  (/health, MCP em /mcp)
```

Verifique a instalação:

```bash
curl http://localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok"}
```

### Indexar a base de conhecimento

```bash
python -m ocean.ingestion.run knowledge_refresh
```

Os arquivos de `content/knowledge/*.md` vêm marcados `revisado: nao`: são rascunhos a revisar com fonte oficial.
A coleção padrão é `ocean_conhecimento` (não mexe na coleção antiga `conhecimento_maritimo`).

### Banco de dados local ou no Neon

Copie a URL PostgreSQL fornecida pelo painel do Neon ou Supabase para `DATABASE_URL` no `.env`.
Em conexões externas, normalmente a URL inclui `sslmode=require`.

```bash
python -m ocean.storage.postgres.migrate      # aplica migrations/*.sql
python -m ocean.ingestion.run ping            # confere a conexão e registra uma execução
```

Após configurar o segredo `DATABASE_URL_ADMIN`, os mesmos migrations e jobs podem rodar pelo
workflow **Ingestão** em **Actions → Ingestão → Run workflow**.

## Ferramentas MCP

| Ferramenta | Situação |
|---|---|
| `search_maritime_knowledge`, `list_knowledge_topics` | implementadas (aliases temporários: `buscar_conhecimento`, `listar_topicos`) |
| `get_tide_table`, `get_marine_conditions` | fase 2 |
| `get_fishing_closures` | fase 3 |
| `search_vessels` | fase 4 |
| `find_fish_markets` | fase 5 |

## Deploy

### Servidor MCP no Render

1. Clique em **New → Blueprint**.
2. Selecione o repositório e o arquivo `render.yaml`.
3. Preencha todas as variáveis marcadas `sync: false`.
4. Defina `MCP_AUTH_TOKEN` com o mesmo valor usado pela API consumidora.
5. Configure `DATABASE_URL` com uma conta PostgreSQL somente leitura.
6. Aguarde o health check em `/health`.

Na API separada `ocean-agent-api`, configure `MCP_SERVER_URL` com o endereço público do MCP
e `ALLOWED_TOOLS` com a lista de ferramentas disponíveis.

### Banco no Neon

O PostgreSQL fica em uma instância do Neon. Copie a URL de conexão do painel (com
`sslmode=require`) para `DATABASE_URL` e aplique o esquema com
`python -m ocean.storage.postgres.migrate`. Crie um usuário somente leitura para o servidor e
use a URL administrativa apenas no GitHub Actions (`DATABASE_URL_ADMIN`).
Nunca copie as credenciais para o repositório ou para comentários.

### Ingestão no GitHub Actions

Crie os secrets administrativos descritos acima e execute
**Actions → Ingestão → Run workflow**, escolhendo o job desejado.

## Documentação

Visão do projeto e guia técnico (decisões, contrato, plano por fases): documentos "Ocean — Visão do Projeto"
e "Ocean — Guia Técnico".
