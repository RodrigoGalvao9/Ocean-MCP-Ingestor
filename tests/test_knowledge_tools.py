from ocean.server.tools import knowledge


def test_search_returns_contract(monkeypatch):
    monkeypatch.setattr(
        knowledge, "search", lambda q, k: [{"id": "x", "title": "T", "text": "t", "score": 1.0}]
    )
    r = knowledge.search_maritime_knowledge("o que é preamar?", k=99)
    assert r["status"] == "ok" and r["freshness"] == "reference"
    assert r["data"]["results"][0]["id"] == "x"
    assert r["limitations"]


def test_search_without_results_is_partial(monkeypatch):
    monkeypatch.setattr(knowledge, "search", lambda q, k: [])
    assert knowledge.search_maritime_knowledge("zzz")["status"] == "partial"


def test_search_failure_becomes_unavailable(monkeypatch):
    def boom(q, k):
        raise RuntimeError("qdrant fora")

    monkeypatch.setattr(knowledge, "search", boom)
    r = knowledge.search_maritime_knowledge("x")
    assert r["status"] == "unavailable" and r["data"] == {}


def test_k_is_clamped(monkeypatch):
    seen = {}
    monkeypatch.setattr(knowledge, "search", lambda q, k: seen.setdefault("k", k) and [])
    knowledge.search_maritime_knowledge("x", k=999)
    assert seen["k"] == 8
