from fastapi.testclient import TestClient

from main import app
from misc.card_generator import INFO_TYPES, generate_card, validate_card_payload
from misc.incident_tree_api import classifier_leaves, load_incident_graph

client = TestClient(app)

BARE_SERVICE_NUMBERS = ("101", "102", "103", "104")


def test_generate_seed_deterministic():
    first = generate_card(seed=12345)["payload"]
    second = generate_card(seed=12345)["payload"]
    assert first == second


def test_generate_valid_cards_bulk():
    for seed in range(50):
        payload = generate_card(seed=seed)["payload"]
        assert validate_card_payload(payload) == "", f"seed={seed}"
        assert payload["what"]
        assert payload["what"] not in BARE_SERVICE_NUMBERS
        assert payload["caller_name"].strip()
        assert payload["caller_status"]
        assert payload["address"]
        assert isinstance(payload["services"], list)
        assert isinstance(payload["factors"], list)


def test_generate_classifier_cards_shape():
    graph = load_incident_graph()
    codes = {leaf["code"] for leaf in classifier_leaves(graph)}
    names = {
        (s["catalog"] or s["title"]) for s in graph["classifier"]["services"]
    }
    seen_classifier = seen_info = 0
    for seed in range(100):
        payload = generate_card(seed=seed)["payload"]
        if payload.get("classifier_code"):
            seen_classifier += 1
            assert payload["classifier_code"] in codes
            assert len(payload["classifier_path"]) >= 1
            assert payload["tags"]["attr1"]
            assert payload["incident_category"]
            assert payload["classifier_section"]["g"] in range(1, 25)
            for service in payload["services"]:
                assert service in names, service
            assert payload["factors"]
        else:
            seen_info += 1
            assert payload["what"] in INFO_TYPES
            assert payload["services"] == []
    assert seen_classifier > 0 and seen_info > 0


def test_generate_type_override_by_code_and_result():
    by_code = generate_card(seed=1, overrides={"type": "1010101"})["payload"]
    assert by_code["classifier_code"] == "1010101"
    assert by_code["what"] == "пожар: мусор"
    by_result = generate_card(seed=1, overrides={"type": "пожар: мусор"})["payload"]
    assert by_result["classifier_code"] == "1010101"


def test_api_generate_returns_new_shape():
    first = client.get("/api/scenarios/generate", params={"seed": 42, "count": 2})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["seed"] == 42
    assert body["count"] == 2
    for card in body["cards"]:
        assert validate_card_payload(card["payload"]) == ""
        assert card["payload"]["what"] not in BARE_SERVICE_NUMBERS

    second = client.get("/api/scenarios/generate", params={"seed": 42, "count": 2})
    assert second.json()["cards"] == body["cards"]


def test_api_generate_type_override():
    response = client.get(
        "/api/scenarios/generate", params={"seed": 1, "type": "1010101"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["cards"][0]["payload"]["classifier_code"] == "1010101"

    bad = client.get("/api/scenarios/generate", params={"type": "нет такого типа"})
    assert bad.status_code == 400


def test_api_generate_publish_creates_scenario():
    response = client.get(
        "/api/scenarios/generate",
        params={"seed": 777001, "count": 1, "publish": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["published"] is True
    assert len(body["scenario_ids"]) == 1

    scenario = client.get(f"/api/scenarios/{body['scenario_ids'][0]}")
    assert scenario.status_code == 200
    data = scenario.json()
    assert data["from_card"] is True
    assert data["expected"]["incident_category"] in (
        "fire", "police", "ambulance", "gas", "dth",
    )


def test_informed_never_dispatched():
    from misc.incident_tree_api import get_classifier

    graph = load_incident_graph()
    informed_names = {
        (s["catalog"] or s["title"])
        for s in get_classifier(graph)["services"]
        if not s.get("auto")
    }
    assert "Аппарат МЭРА" in informed_names
    for seed in range(100):
        payload = generate_card(seed=seed)["payload"]
        assert "services_informed" not in payload
        for service in payload["services"]:
            assert service not in informed_names, (seed, service)
