# Configuração

## Ambiente local

Crie o arquivo `.env` a partir do exemplo:

```powershell
Copy-Item .env.example .env
```

Nunca versionar o `.env` nem reutilizar credenciais de outro ambiente.

## Variáveis do servidor

| Variável | Finalidade |
|---|---|
| `ENVIRONMENT` | Ambiente da aplicação; use `production` no deploy |
| `LOG_LEVEL` | Nível de logging, normalmente `INFO` |
| `MCP_AUTH_TOKEN` | Token Bearer para proteger o servidor MCP |
| `MCP_HOST` | Host de escuta local, padrão `0.0.0.0` |
| `PORT` | Porta HTTP, padrão `8000` |
| `DATABASE_URL` | PostgreSQL usado pelo servidor, preferencialmente somente leitura |
| `REDIS_URL` | Cache de condições marítimas |
| `QDRANT_URL` | Endpoint do Qdrant |
| `QDRANT_API_KEY` | Chave do Qdrant |
| `QDRANT_COLLECTION` | Coleção vetorial, padrão `ocean_conhecimento` |
| `CLOUDFLARE_ACCOUNT_ID` | Conta para geração de embeddings |
| `CLOUDFLARE_API_TOKEN` | Token Cloudflare com acesso ao modelo |

## Variáveis exclusivas da ingestão

| Variável | Uso |
|---|---|
| `DATABASE_URL_ADMIN` | URL administrativa usada por migrations e GitHub Actions |
| `GFW_TOKEN` | Token reservado para integrações do Global Fishing Watch |
| `FASTEMBED_CACHE_DIR` | Diretório opcional do cache local de embeddings |

O servidor público não deve usar `DATABASE_URL_ADMIN`. No GitHub Actions, os secrets são
injetados como variáveis de ambiente pelo workflow de ingestão.
