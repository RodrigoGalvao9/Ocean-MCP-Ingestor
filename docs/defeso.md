# Defesos (fase 3): carga local

Os defesos vêm de duas fontes oficiais e são carregados **da sua máquina para o banco**. Nada de
`data/` (raiz) vai ao Git.

| Arquivo em `data/defeso/` | Origem |
|---|---|
| `defeso_closures.csv`, `defeso_areas.csv` | Tabela do MPA por município, lida por `defeso_municipal` |
| `curated_closures.csv`, `curated_areas.csv` | Curadoria a partir das normas (caranguejo-uçá, camarão zona I em AL/SE) |

Basta um dos pares. Quando um defeso aparece nos dois (mesma norma, espécie, nome científico, período e ano), valem as
áreas somadas e os dados do curado.

## Comandos (PowerShell, na raiz do projeto)

```powershell
# 1) Banco administrativo (Neon): aplica a migration 0002
$env:DATABASE_URL = "<url administrativa do Neon>"
python -m ocean.storage.postgres.migrate

# 2) Tabela do MPA -> CSVs (aplica src/ocean/data/defeso_overrides.csv por padrão)
python -m ocean.ingestion.parsers.defeso_municipal "Tabela_defesos_MUN_ASCOM_v003_12.08.2026.pdf.txt" `
  --out-dir data/defeso --verified-at 2026-08-12 --label "MPA v003 de 12/08/2026"

# 3) Coloque curated_closures.csv e curated_areas.csv em data/defeso/, depois:
python -m ocean.ingestion.run mpa_closures
```

A carga é **completa**: repetir o comando atualiza o que mudou e remove do banco o que saiu dos
CSVs. Se nenhum CSV for encontrado, o job falha sem tocar no banco.

## Correções pela norma

A tabela do MPA tem erros (ex.: camarão da zona I com fim em 15/03 em vez de 15/01; data 31/11).
`src/ocean/data/defeso_overrides.csv` guarda cada correção com o motivo e a norma. Para conferir
uma data, consulte o PDF da norma em
https://www.gov.br/ibama/pt-br/assuntos/biodiversidade/biodiversidade-aquatica/periodos-de-defeso/defesos-marinhos

## Normas nacionais e por faixa do litoral

A tabela do MPA lista somente municípios abrangidos ou limítrofes e não representa toda a área
coberta por certas normas. Por isso, o parser exclui por padrão garoupa-verdadeira, caranha/sirigado,
gurijuba, lagosta, pargo e caranguejo-uçá; esses defesos entram pelo CSV curado.

No CSV curado, `uf = BR` representa uma norma nacional válida em todo o litoral. Uma UF com
`ibge_code` vazio representa o estado inteiro.

## Consulta

A ferramenta `get_fishing_closures(place, species=None, date=None, days_ahead=90)` consulta
defesos em vigor, próximos defesos e defesos definidos para municípios ou estados específicos.
Defesos com `year` valem somente no ano informado. Resultado parcial significa que o banco não
contém cobertura suficiente e não prova que a pesca esteja liberada.
