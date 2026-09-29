from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_sections():
    response = client.get("/api/classifier/sections")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 23
    filled = [s for s in body if s["filled"]]
    assert [s["g"] for s in filled] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert sum(s["leaf_count"] for s in body) == 509


def test_search_finds_classifier_result():
    response = client.get("/api/classifier/search", params={"q": "мусор"})
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items
    assert items[0]["code"] == "1010101"
    assert items[0]["result"] == "пожар: мусор"
    assert items[0]["path"] == ["на улице", "мусор", "открытое пламя"]


def test_leaf_and_dispatch():
    leaf = client.get("/api/classifier/leaf/1010101")
    assert leaf.status_code == 200, leaf.text
    assert leaf.json()["leaf"]["result"] == "пожар: мусор"

    dispatch = client.get("/api/classifier/dispatch", params={"code": "1010101"})
    assert dispatch.status_code == 200, dispatch.text
    services = dispatch.json()["services"]
    assert services
    assert services[0].startswith("Служба 101")

    flagged = client.get(
        "/api/classifier/dispatch", params={"code": "1010101", "victims": True}
    )
    assert flagged.status_code == 200
    assert flagged.json()["services"]


def test_unknown_code_404():
    assert client.get("/api/classifier/leaf/0000000").status_code == 404
    assert client.get("/api/classifier/dispatch", params={"code": "0000000"}).status_code == 404
