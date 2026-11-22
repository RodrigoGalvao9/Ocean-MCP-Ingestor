# Ocean MCP + Ingestor

> Dados marítimos brasileiros para agentes de IA: condições do mar, marés e conhecimento
> operacional em uma interface MCP somente leitura.

[![CI](https://github.com/RodrigoGalvao9/Ocean-MCP-Ingestor/actions/workflows/ci.yml/badge.svg)](https://github.com/RodrigoGalvao9/Ocean-MCP-Ingestor/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/Protocol-MCP-5B5BD6)](https://modelcontextprotocol.io/)

O **Ocean** conecta aplicações de IA a informações marítimas brasileiras com respostas
estruturadas, proveniência e limitações explícitas. O servidor alimenta o
[`ocean-agent-api`](https://github.com/RodrigoGalvao9/ocean-agent-api) e pode ser executado
localmente ou hospedado em nuvem.

## Por que usar

| Capacidade | Benefício |
|---|---|
| MCP padronizado | Integração direta com agentes e clientes compatíveis com MCP |
| Dados marítimos | Condições do mar e tábuas de maré para locais brasileiros |
| Respostas confiáveis | Fonte, momento da consulta, atualidade e limitações no retorno |
| Arquitetura modular | PostgreSQL, Qdrant, Redis e fontes ao vivo sem acoplamento indevido |
| Operação segura | Servidor de consulta sem operações de escrita para consumidores |

## Funcionalidades disponíveis

| Ferramenta | O que entrega | Status |
|---|---|---|
| `get_marine_conditions` | Vento, rajadas, ondas, temperatura e previsão | Disponível |
| `get_tide_table` | Estação DHN mais próxima, fase e eventos de maré | Disponível |
| `search_maritime_knowledge` | Busca semântica em conteúdo marítimo | Disponível |
| `list_knowledge_topics` | Lista os tópicos indexados | Disponível |
| `get_fishing_closures` | Períodos de defeso | Planejada |
| `search_vessels` | Busca de embarcações | Planejada |
| `find_fish_markets` | Locais para comercialização de pescado | Planejada |

## Início rápido

Requisitos: Python 3.12 e, para o servidor completo, as credenciais descritas em
[`docs/configuration.md`](docs/configuration.md).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[server,ingest,dev]"
Copy-Item .env.example .env
python -m ocean.server
```

O servidor ficará disponível em `http://localhost:8000`. Verifique a saúde da aplicação:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Consulte exemplos completos de inicialização MCP e chamadas JSON em
[`docs/mcp.md`](docs/mcp.md).

## Arquitetura em uma visão

```text
Cliente MCP / ocean-agent-api
             |
             v
       Servidor Ocean
       /health  /mcp
       |        |
       |        +--> Ferramentas de consulta
       |              |--> Open-Meteo (condições)
       |              |--> PostgreSQL (marés e dados estruturados)
       |              |--> Qdrant + embeddings (conhecimento)
       |              +--> Redis (cache)
       |
       +--> Ingestão local ou GitHub Actions
             |--> PDFs/CSV da DHN
             |--> Conteúdo de conhecimento
             +--> PostgreSQL e Qdrant
```

O servidor público usa uma conta de banco somente leitura. A ingestão e as migrations usam
credenciais administrativas separadas. Para decisões de arquitetura, consulte
[`docs/architecture.md`](docs/architecture.md).

## Documentação

| Guia | Público |
|---|---|
| [`docs/mcp.md`](docs/mcp.md) | Consumidores MCP e integração |
| [`docs/configuration.md`](docs/configuration.md) | Variáveis de ambiente e configuração |
| [`docs/development.md`](docs/development.md) | Contribuidores e desenvolvimento local |
| [`docs/operations.md`](docs/operations.md) | Execução, deploy e observabilidade |
| [`docs/ingestion.md`](docs/ingestion.md) | Jobs, GitHub Actions e cargas |
| [`docs/mares-csv.md`](docs/mares-csv.md) | Conversão das tábuas DHN para CSV |
| [`docs/dados.md`](docs/dados.md) | Dados curados e contratos de CSV |
| [`docs/architecture.md`](docs/architecture.md) | Limites e decisões técnicas |

## Fontes e limitações

As respostas não substituem avisos oficiais da Marinha do Brasil. Condições meteorológicas e
ondas vêm de modelos numéricos; marés são previsões astronômicas e podem sofrer influência de
vento, pressão, chuva e vazão de rios.

Open-Meteo e GFW possuem regras de atribuição e uso não comercial. Antes de oferecer o serviço
a terceiros, confira os termos de cada fonte. O projeto é somente leitura para seus
consumidores e não garante segurança de navegação.

## Licença e contribuição

Antes de redistribuir dados de terceiros, confirme as licenças e os termos das fontes. Para
executar a validação local, siga [`docs/development.md`](docs/development.md). Pull requests
devem preservar os contratos de proveniência e as regras de importação do projeto.
