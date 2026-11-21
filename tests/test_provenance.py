import json

from ocean.shared.provenance import Freshness, MaritimeDataResponse, Status


def test_tool_result_is_plain_json():
    r = MaritimeDataResponse(
        status=Status.OK, source="Fonte X", freshness=Freshness.LIVE, data={"a": 1}
    )
    payload = r.to_tool_result()
    json.dumps(payload)  # não pode lançar
    assert payload["status"] == "ok" and payload["freshness"] == "live"
    assert payload["retrieved_at"].endswith(("Z", "+00:00"))


def test_unavailable_carries_reason():
    r = MaritimeDataResponse.unavailable("Fonte X", "fora do ar")
    assert r.status is Status.UNAVAILABLE and r.limitations == ["fora do ar"]
