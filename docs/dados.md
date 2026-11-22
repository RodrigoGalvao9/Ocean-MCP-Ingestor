# Dados curados

Este documento descreve contratos de dados usados pelos jobs planejados e implementados.

`fish_markets.csv`: tabela de onde vender pescado (região piloto: Nordeste).
Cada linha precisa de **fonte** e **data de verificação** (`verified_at`, AAAA-MM-DD).
`kind`: terminal pesqueiro, mercado, entreposto, colônia, etc.
Carregada no Postgres pelo job `markets_load` (fase 5, ainda planejado).

## Regras gerais

- Use UTF-8.
- Preserve a fonte original.
- Informe a data de verificação em `AAAA-MM-DD`.
- Não adicione credenciais, tokens ou dados pessoais desnecessários.
