# Dados curados

`fish_markets.csv`: tabela de onde vender pescado (região piloto: Nordeste).
Cada linha precisa de **fonte** e **data de verificação** (`verified_at`, AAAA-MM-DD).
`kind`: terminal pesqueiro, mercado, entreposto, colônia, etc.
Carregada no Postgres pelo job `markets_load` (fase 5).
