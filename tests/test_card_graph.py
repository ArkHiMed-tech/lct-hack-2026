from fastapi.testclient import TestClient

from main import app
from misc.card_graph import generate_batch, generate_card, walk

client = TestClient(app)


def test_generate_card_has_report_shape():
    card = generate_card(seed=42)
    for key in ("what", "incident_category", "address", "caller_name",
                "tags", "services", "description"):
        assert key in card
    assert card["what"] and card["address"] and card["caller_name"]


def test_walk_info_type_has_no_services():
    ctx = walk(seed=0, fixed_type="Тестовый вызов")
    assert ctx["services"] == []
    assert set(ctx["tags"]) == {"tagDesc"}


def test_generate_deterministic():
    assert generate_card(seed=7) == generate_card(seed=7)
    assert len(generate_batch(3, seed=1)) == 3


def test_cards_api():
    assert client.get("/api/cards/graph").status_code == 200
    r = client.get("/api/cards/generate", params={"count": 2, "seed": 7})
    assert r.status_code == 200
    assert r.json()["count"] == 2
    r = client.post("/api/cards/generate", json={"count": 1, "seed": 3})
    assert r.status_code == 200
