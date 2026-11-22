# Operação e deploy

## Executar localmente

```powershell
.\.venv\Scripts\Activate.ps1
python -m ocean.server
```

O servidor MCP fica em `http://localhost:8000/mcp` e o health check público em
`http://localhost:8000/health`.

```powershell
Invoke-RestMethod http://localhost:8000/health
```

Resposta esperada:

```json
{"status":"ok"}
```

## Limite do Open-Meteo

O plano público do Open-Meteo é destinado a uso não comercial e possui limite de chamadas.
Quando o provedor responde `HTTP 429`, a ferramenta retorna `status: "unavailable"` com essa
causa explícita e não repete imediatamente a mesma requisição.

Em produção:

1. Configure `REDIS_URL` para compartilhar o cache entre reinícios e instâncias.
2. Evite chamadas repetidas para o mesmo local; o cache de condições tem validade de 30 minutos.
3. Aguarde o limite ser liberado antes de testar novamente após um `429`.
4. Para volume maior ou uso comercial, contrate uma cota adequada no Open-Meteo e siga os
   termos de atribuição e licença do provedor.

## Deploy no Render

O [`render.yaml`](../render.yaml) define o servidor como um serviço Docker com health check em
`/health`. A ingestão não roda no Render; ela é executada pelo GitHub Actions.

1. Crie um Blueprint no Render apontando para este repositório.
2. Preencha as variáveis marcadas com `sync: false`.
3. Use o mesmo `MCP_AUTH_TOKEN` na API consumidora e no servidor.
4. Configure `DATABASE_URL` com um usuário PostgreSQL somente leitura.
5. Configure `REDIS_URL` com a Internal URL do Key Value na mesma região.
6. Valide o health check antes de conectar o cliente MCP.

## Banco e migrations

Aplique migrations com uma URL administrativa:

```powershell
$env:DATABASE_URL = "<url administrativa do Neon>"
python -m ocean.storage.postgres.migrate
```

Não use uma URL administrativa no servidor público.

## Segurança operacional

- Não versionar `.env`, tokens ou URLs com credenciais.
- Não expor `DATABASE_URL_ADMIN` ao servidor MCP.
- Manter `MCP_AUTH_TOKEN` configurado em produção.
- Consultar as licenças e limites das fontes externas antes de uso comercial.
