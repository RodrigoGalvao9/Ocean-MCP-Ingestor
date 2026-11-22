# Eventos de maré (preamar e baixa-mar)

## Gerar os CSVs a partir dos PDFs da DHN

```
pip install -e ".[ingest]"
python -m ocean.ingestion.parsers.dhn_tides_pdf pasta/*.pdf --stations data/tide_stations.csv --out-dir data/tides
```

O script lê o cabeçalho de cada PDF (porto, UF, coordenadas, fuso, carta), cria ou atualiza a
linha da estação e escreve `data/tides/<id>-<ano>.csv`. Preamar e baixa-mar não vêm rotuladas
na tábua: o tipo é deduzido comparando cada altura com as vizinhas. Erros de leitura (dia
ausente, linha ilegível) geram código de saída 1 e nenhum arquivo para aquele PDF; falhas da
própria tábua (um evento faltando) viram avisos e a carga segue.

Cada arquivo `*.csv` desta pasta é carregado pelo job `tides_yearly`
(`python -m ocean.ingestion.run tides_yearly`). O formato é o mesmo para dados vindos de um
parser de PDF e para tábuas digitadas à mão (plano B do Guia Técnico):

```
station_id,local_datetime,kind,height_m,edition
natal-rn,2026-01-01 03:12,low,0.35,63
natal-rn,2026-01-01 09:31,high,2.41,63
```

- `station_id`: precisa existir em `data/tide_stations.csv`.
- `local_datetime`: horário legal da estação (como está na tábua), `AAAA-MM-DD HH:MM`. O job
  converte para UTC usando o fuso da estação.
- `kind`: `high` (preamar) ou `low` (baixa-mar).
- `height_m`: altura em metros, referida ao nível de redução da carta, como na tábua.
- `edition`: número da edição da publicação (opcional).

Transcreva somente valores de uma tábua oficial (Marinha do Brasil, DHN/CHM) e confira
os termos de uso da publicação antes de versionar os arquivos neste repositório [verificar].
O job é idempotente: carregar o mesmo arquivo duas vezes não duplica linhas.
