# Ingestão

A ingestão prepara dados para o servidor MCP. Ela pode rodar localmente ou no GitHub Actions e
não é importada pelo módulo do servidor.

## Jobs disponíveis

```powershell
python -m ocean.ingestion.run ping
python -m ocean.ingestion.run knowledge_refresh
python -m ocean.ingestion.run tides_yearly
```

Os jobs `mpa_closures`, `mpa_registry` e `markets_load` fazem parte do roadmap e só devem ser
executados quando estiverem implementados e com os dados correspondentes disponíveis.

## GitHub Actions

O workflow [`ingest.yml`](../.github/workflows/ingest.yml) recebe o job por `workflow_dispatch`.
Configure estes secrets no repositório:

- `DATABASE_URL_ADMIN`
- `QDRANT_URL`
- `QDRANT_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_API_TOKEN`

O workflow aplica as migrations e executa o job escolhido. `tides_yearly` fica fora do workflow
porque os CSVs de maré não são versionados; siga [`mares-csv.md`](mares-csv.md) para a carga
local.

## Conhecimento marítimo

Atualize os documentos em `content/knowledge/` e execute:

```powershell
python -m ocean.ingestion.run knowledge_refresh
```

A coleção padrão é `ocean_conhecimento`.

## Marés

O fluxo completo para converter PDFs oficiais da DHN, validar CSVs e carregar as previsões está
em [`mares-csv.md`](mares-csv.md).
