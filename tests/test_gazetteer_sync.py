import csv

from ocean.ingestion.parsers import gazetteer_sync as gs

HEADER = "name,uf,kind,latitude,longitude,aliases\n"


def _station(sid, name, uf, lat, lon):
    return {"id": sid, "name": name, "uf": uf, "latitude": str(lat), "longitude": str(lon)}


def _gazetteer(tmp_path, body=""):
    path = tmp_path / "gazetteer.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


def test_base_name():
    assert gs.base_name("Porto de Natal") == "Natal"
    assert gs.base_name("Porto do Recife") == "Recife"
    assert gs.base_name("Terminal da Ponta do Ubu") == "Ponta do Ubu"
    assert gs.base_name("Porto de Suape - Cais 4") == "Suape"
    assert gs.base_name("Ilha Fiscal") == "Ilha Fiscal"


def test_propose_new_existing_conflict_and_out_of_bounds(tmp_path):
    path = _gazetteer(tmp_path, "Recife,PE,cidade,-8.05,-34.88,\nSão José,SC,cidade,-27.6,-48.6,\n")
    known = gs.read_gazetteer_names(path)
    stations = [
        _station("macau-rn", "Porto de Macau", "RN", -5.10, -36.67),
        _station("recife-pe", "Porto do Recife", "PE", -8.05, -34.87),
        _station("sj-ma", "Porto de São José", "MA", -2.5, -44.0),
        _station("ant", "Estação Antártica", "AQ", -62.0, -58.0),
        _station("macau-2", "Porto de Macau", "RN", -5.11, -36.66),
    ]
    proposals, skipped = gs.propose(stations, known)
    assert [p.row["name"] for p in proposals] == ["Macau"]
    assert proposals[0].row["aliases"] == "Porto de Macau"
    reasons = {s.station_id: s.reason for s in skipped}
    assert reasons["recife-pe"] == "já existe"
    assert reasons["sj-ma"] == "nome já usado em SC"
    assert reasons["ant"] == "fora da faixa do Brasil"
    assert reasons["macau-2"] == "já existe"  # duplicata dentro da própria lista


def test_main_dry_run_then_write(tmp_path, capsys):
    gaz = _gazetteer(tmp_path, "Recife,PE,cidade,-8.05,-34.88,")  # sem quebra de linha final
    stations = tmp_path / "stations.csv"
    stations.write_text(
        "id,name,uf,latitude,longitude\nmacau-rn,Porto de Macau,RN,-5.10,-36.67\n",
        encoding="utf-8",
    )
    args = ["--stations", str(stations), "--gazetteer", str(gaz)]
    before = gaz.read_text(encoding="utf-8")

    assert gs.main(args) == 0
    assert gaz.read_text(encoding="utf-8") == before  # simulação não grava
    assert "Simulação" in capsys.readouterr().out

    assert gs.main([*args, "--write"]) == 0
    rows = list(csv.DictReader(gaz.open(encoding="utf-8")))
    assert [r["name"] for r in rows] == ["Recife", "Macau"]
    assert rows[1]["kind"] == "porto" and rows[1]["latitude"] == "-5.1000"

    assert gs.main([*args, "--write"]) == 0  # idempotente
    assert len(list(csv.DictReader(gaz.open(encoding="utf-8")))) == 2


def test_main_missing_stations(tmp_path):
    assert gs.main(["--stations", str(tmp_path / "nao-existe.csv")]) == 1


def test_main_reads_stations_from_database_by_default(tmp_path, monkeypatch):
    gaz = _gazetteer(tmp_path)
    monkeypatch.setattr(
        gs, "load_stations_db", lambda: [_station("macau-rn", "Porto de Macau", "RN", -5.1, -36.67)]
    )
    assert gs.main(["--gazetteer", str(gaz), "--write"]) == 0
    assert [r["name"] for r in csv.DictReader(gaz.open(encoding="utf-8"))] == ["Macau"]


def test_main_database_failure_is_reported(tmp_path, monkeypatch, capsys):
    def boom():
        raise RuntimeError("DATABASE_URL não definido")

    monkeypatch.setattr(gs, "load_stations_db", boom)
    assert gs.main(["--gazetteer", str(_gazetteer(tmp_path))]) == 1
    assert "DATABASE_URL" in capsys.readouterr().err
