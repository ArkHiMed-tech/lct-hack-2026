from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_sections():
    response = client.get("/api/classifier/sections")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == 24
    filled = [s for s in body if s["filled"]]
    assert [s["g"] for s in filled] == list(range(1, 25))
    assert sum(s["leaf_count"] for s in body) == 1283


def test_search_finds_classifier_result():
    response = client.get("/api/classifier/search", params={"q": "мусор"})
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items
    codes = [i["code"] for i in items]
    assert "1010101" in codes
    first = items[0]
    assert "мусор" in (first["result"] + " " + " ".join(first["path"])).lower()


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


def test_tree_roots_are_all_sections():
    response = client.get("/api/classifier/tree")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["levels"] == ["section", "p1", "p2", "p3"]
    assert body["level_labels"] == {
        "section": "Раздел", "p1": "Место", "p2": "Что", "p3": "Проявление",
    }
    assert len(body["roots"]) == 24
    assert body["roots"][0]["title"] == "Пожары и задымления"
    assert body["roots"][-1]["title"] == "БПЛА"


def test_children_cascade():
    step0 = client.get("/api/classifier/children")
    assert step0.status_code == 200
    assert len(step0.json()["buttons"]) == 24

    step1 = client.get("/api/classifier/children", params={"g": 1})
    assert step1.status_code == 200
    assert [b["value"] for b in step1.json()["buttons"]] == [
        "на улице", "транспорт", "метро", "МЦК", "жилой дом", "объект",
    ]

    step3 = client.get(
        "/api/classifier/children",
        params={"g": 1, "p1": "на улице", "p2": "мусор", "p3": "дым"},
    )
    assert step3.status_code == 200
    assert step3.json()["buttons"] == []
    assert step3.json()["selectable"] == [
        {"code": "1010102", "result": "задымление: мусор"}
    ]

    bad = client.get("/api/classifier/children", params={"g": 99})
    assert bad.status_code == 200
    assert bad.json()["buttons"] == []


def test_breadcrumb():
    response = client.get("/api/classifier/breadcrumb/1010101")
    assert response.status_code == 200, response.text
    crumbs = response.json()["breadcrumb"]
    assert [c["value"] for c in crumbs] == [
        "Пожары и задымления", "на улице", "мусор", "открытое пламя",
    ]
    assert client.get("/api/classifier/breadcrumb/0000000").status_code == 404


def test_dispatch_returns_informed_blue():
    response = client.get("/api/classifier/dispatch", params={"code": "1010101"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["services"][0].startswith("Служба 101")
    assert "Аппарат МЭРА" in body["informed"]
    assert "Аппарат МЭРА" not in body["services"]
    assert body["detail"]["mchs101"]["mode"] == "respond"
    for gid, item in body["detail"].items():
        if item["display"] == "Аппарат МЭРА":
            assert item["mode"] == "informed"


def test_dispatch_strict_nd():
    plain = client.get("/api/classifier/dispatch", params={"code": "1010101"})
    flagged = client.get("/api/classifier/dispatch", params={"code": "1010101", "nd": True})
    assert flagged.status_code == 200
    assert any(s.startswith("Служба 101") for s in plain.json()["services"])
    assert not any(s.startswith("Служба 101") for s in flagged.json()["services"])
