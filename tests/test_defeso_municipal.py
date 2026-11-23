# ruff: noqa: E501
import csv
import os
from pathlib import Path

import pytest

from ocean.ingestion.parsers import defeso_municipal as dm

HEADER = (
    "MINISTÉRIO DA PESCA E AQUICULTURA\n"
    "Lista nominal de municípios abrangidos ou limítrofes associados a cada período de defeso "
    "vigente\n\n"
    "ID PORTARIA PERIODO ESPECIE (S) AMBIENTE UF NOME MUNICIPIO COD_IBGE_MUN\n"
)
SAMPLE = (
    HEADER
    + """\
1 Portaria IBAMA 1-N/96 01/03-30/04 Todas as espécies ocorrentes nos Rios Continental PB Aguiar 2500205
76 Portaria SAP/MAPA nº 221/2021 1/11-30/4 Lagosta vermelha (Panulirus argus), verde (Panulirus
laevicauda), pintada (Panulirus echinatus)
Marinho PE Recife 2611606
76 Portaria SAP/MAPA nº 221/2021 1/11-30/4 Lagosta vermelha (Panulirus argus), verde (Panulirus
laevicauda), pintada (Panulirus echinatus)
Marinho RN Natal 2408102
69 Portaria Interministerial SG/MMA nº 41/2018 1/11-28/2 Garoupa-verdadeira (Epinephelus marginatus) Marinho PE Recife 2611606
74 Portaria SAP/MAPA nº 325/2020
30/12-4/1
13/1-18/1
Caranguejo-uçá (Ucides cordatus)
Marinho PE Recife 2611606
56 IN MMA nº 14/05 15/9-31/11 Camarão-rosa Marinho BA Salvador 2927408
53 IN MMA nº 14/04 1/12-15/03 Camarão-rosa Marinho BA Salvador 2927408
"""
)


def test_split_period_and_invalid_dates():
    assert dm.split_period("1/11-30/4") == ("11-01", "04-30")
    assert dm.split_period("1/12-29/2") == ("12-01", "02-29")
    with pytest.raises(dm.DefesoTableError):
        dm.split_period("15/9-31/11")


def test_read_records_joins_wrapped_lines():
    records = dm.read_records(SAMPLE)
    assert len(records) == 7
    assert records[1].startswith("76 Portaria SAP/MAPA nº 221/2021 1/11-30/4 Lagosta vermelha")
    assert records[1].endswith("Marinho PE Recife 2611606")


def test_parse_marine_only_skips_caranguejo_and_groups_municipalities():
    closures, warnings = dm.parse(SAMPLE)
    by_act = {c.act_id: c for c in closures}
    assert set(by_act) == {"76", "69", "53"}  # 1 continental, 74 caranguejo, 56 inválido: fora
    lagosta = by_act["76"]
    assert (lagosta.start, lagosta.end) == ("11-01", "04-30")
    assert lagosta.areas == {("PE", "2611606"): "Recife", ("RN", "2408102"): "Natal"}
    assert any("31/11" in w for w in warnings)


def test_overrides_fix_and_drop(tmp_path):
    path = tmp_path / "o.csv"
    path.write_text(
        "act_id,period,new_period,reason\n53,1/12-15/03,1/12-15/01,norma\n56,15/9-31/11,,typo\n",
        encoding="utf-8",
    )
    closures, warnings = dm.parse(SAMPLE, overrides=dm.load_overrides(path))
    by_act = {c.act_id: c for c in closures}
    assert (by_act["53"].start, by_act["53"].end) == ("12-01", "01-15")
    assert "56" not in by_act and not any("31/11" in w for w in warnings)


def test_override_requires_reason(tmp_path):
    path = tmp_path / "o.csv"
    path.write_text(
        "act_id,period,new_period,reason\n53,1/12-15/03,1/12-15/01,\n", encoding="utf-8"
    )
    with pytest.raises(dm.DefesoTableError):
        dm.load_overrides(path)


def test_packaged_overrides_are_valid():
    overrides = dm.load_overrides(dm.default_overrides_path())
    assert overrides[("53", "1/12-15/03")][0] == "1/12-15/01"
    for new_period, _ in overrides.values():
        if new_period:
            dm.split_period(new_period)


def test_unrecognized_record_is_an_error():
    with pytest.raises(dm.DefesoTableError):
        dm.parse(HEADER + "isto não é um registro 1234567\n")


def test_leftover_text_is_an_error():
    with pytest.raises(dm.DefesoTableError):
        dm.read_records(HEADER + "1 Portaria X 1/1-2/2 Espécie Marinho PE Recife\n")


def test_main_writes_csvs(tmp_path):
    table = tmp_path / "t.txt"
    table.write_text(SAMPLE, encoding="utf-8")
    out = tmp_path / "out"
    assert dm.main([str(table), "--out-dir", str(out), "--verified-at", "2026-08-12"]) == 0
    closures = list(csv.DictReader((out / "defeso_closures.csv").open(encoding="utf-8")))
    areas = list(csv.DictReader((out / "defeso_areas.csv").open(encoding="utf-8")))
    lagosta = next(c for c in closures if c["legal_reference"].endswith("221/2021"))
    assert lagosta["environment"] == "marine" and lagosta["last_verified_at"] == "2026-08-12"
    assert {a["municipality"] for a in areas if a["closure_key"] == lagosta["key"]} == {
        "Recife",
        "Natal",
    }
    assert [c["prohibition_end"] for c in closures if c["key"].startswith("mun-53")] == ["01-15"]


def test_main_missing_file(tmp_path):
    assert dm.main([str(tmp_path / "nao.txt")]) == 1


@pytest.mark.skipif(not os.environ.get("DEFESO_TXT"), reason="DEFESO_TXT não definido")
def test_real_table_parses_cleanly():
    text = Path(os.environ["DEFESO_TXT"]).read_text(encoding="utf-8")
    closures, warnings = dm.parse(text, overrides=dm.load_overrides(dm.default_overrides_path()))
    assert closures and not any("descartado" in w for w in warnings)
    assert all(c.areas for c in closures)
