import pytest

from ocean.retrieval.structured import gazetteer


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Recife", "Recife"),
        ("recife, pe", "Recife"),
        ("São Luís - Maranhão", "São Luís"),
        ("sao luis", "São Luís"),
        ("Pipa", "Tibau do Sul"),
        ("Porto de Galinhas", "Ipojuca"),
        ("como está o vento em Salvador hoje?", "Salvador"),
        ("maré baixa em Santos amanhã", "Santos"),
    ],
)
def test_resolve_known(text, expected):
    assert gazetteer.resolve(text).name == expected


@pytest.mark.parametrize("text", ["", "   ", "Atlantida", "Recife, SP"])
def test_resolve_unknown(text):
    assert gazetteer.resolve(text) is None


def test_all_places_have_valid_coordinates_and_pilot_states():
    places = gazetteer.all_places()
    assert {"PE", "BA", "SE", "RN", "MA"} <= {p.uf for p in places}
    for p in places:
        assert -35 < p.latitude < 6 and -75 < p.longitude < -30, p
    assert len({(p.name, p.uf) for p in places}) == len(places)
