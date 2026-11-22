# Integração MCP

Este guia descreve como testar o servidor MCP e chamar as ferramentas do Ocean. O transporte
HTTP usa `POST http://localhost:8000/mcp`.

## Headers

```text
Content-Type: application/json
Authorization: Bearer SEU_MCP_AUTH_TOKEN
```

O header `Authorization` é necessário quando `MCP_AUTH_TOKEN` está configurado. Em
desenvolvimento, o servidor pode ser executado sem autenticação.

## Inicializar uma sessão

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {
      "name": "teste-local",
      "version": "1.0.0"
    }
  }
}
```

## Listar ferramentas

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

## Chamar uma ferramenta

Todas as chamadas usam `method: "tools/call"`:

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "NOME_DA_FERRAMENTA",
    "arguments": {}
  }
}
```

### Conhecimento marítimo

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tools/call",
  "params": {
    "name": "search_maritime_knowledge",
    "arguments": {
      "query": "O que é preamar e baixa-mar?",
      "k": 4
    }
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": 5,
  "method": "tools/call",
  "params": {
    "name": "list_knowledge_topics",
    "arguments": {}
  }
}
```

Aliases temporários em português: `buscar_conhecimento` e `listar_topicos`.

### Condições do mar

```json
{
  "jsonrpc": "2.0",
  "id": 6,
  "method": "tools/call",
  "params": {
    "name": "get_marine_conditions",
    "arguments": {
      "place": "Recife",
      "hours": 24
    }
  }
}
```

`hours` pode variar de `0` a `48`, em intervalos de três horas. Informe o nome do lugar,
não coordenadas. Exemplos: `Recife`, `Salvador`, `Natal`, `Porto Seguro` e `Santos`.

### Tábua de marés

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "get_tide_table",
    "arguments": {
      "place": "Salvador",
      "hours": 36
    }
  }
}
```

Para consultar um dia específico:

```json
{
  "jsonrpc": "2.0",
  "id": 8,
  "method": "tools/call",
  "params": {
    "name": "get_tide_table",
    "arguments": {
      "place": "Santos",
      "hours": 24,
      "date": "2026-11-25"
    }
  }
}
```

`hours` aceita valores de `6` a `168`. A tábua carregada atualmente cobre o ano de 2026.

## Teste pelo PowerShell

Com o ambiente virtual ativado e o servidor em execução:

```powershell
$body = @{
  jsonrpc = "2.0"
  id = 10
  method = "tools/call"
  params = @{
    name = "get_marine_conditions"
    arguments = @{
      place = "Recife"
      hours = 6
    }
  }
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Uri "http://localhost:8000/mcp" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```
