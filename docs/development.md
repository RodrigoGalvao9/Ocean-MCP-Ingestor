# Desenvolvimento

## Requisitos

- Python 3.12
- PostgreSQL 16 para testes de integração
- Redis, Qdrant e credenciais de fontes quando o fluxo exigir esses serviços

## Preparar o ambiente

No Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[server,ingest,dev]"
Copy-Item .env.example .env
```

Depois da instalação, use sempre o interpretador do `.venv`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\lint-imports.exe
```

## Validação local

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\lint-imports.exe
```

O CI executa os mesmos checks e também inicia um PostgreSQL de teste. Os testes de integração
usam `TEST_DATABASE_URL`, cujo banco deve conter `test` no nome.

## Estrutura do código

```text
src/ocean/
  server/       Aplicação MCP, autenticação e health check
  ingestion/    Jobs, coletores e parsers
  domain/       Modelos e regras determinísticas
  retrieval/   Consultas vetoriais e estruturadas
  storage/      PostgreSQL e cache Redis
  shared/       Configuração, HTTP, logging e proveniência
tests/          Testes unitários e de integração
```

## Regras para mudanças

1. O servidor e a ingestão não importam um ao outro.
2. Ferramentas MCP recebem parâmetros simples e retornam `MaritimeDataResponse`.
3. Toda resposta deve informar fonte, momento do dado, atualidade e limitações.
4. Regras determinísticas ficam em `domain/services`, não no agente de linguagem.
5. Não adicionar operações de escrita ao caminho público do servidor.

## Conteúdo da base de conhecimento

Os documentos em `content/knowledge/` são Markdown com metadados de revisão. Após editar o
conteúdo, execute o job `knowledge_refresh` conforme [`ingestion.md`](ingestion.md).
