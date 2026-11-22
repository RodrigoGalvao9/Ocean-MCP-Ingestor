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
