import json
from urllib.error import URLError

from fastapi.testclient import TestClient

from database import get_connection, initialize_database
import main
from main import app

client = TestClient(app)


def test_health_route_exists():
    response = client.get("/api/health")
    assert response.status_code == 200


def test_auth_login_route_exists():
    response = client.post(
        "/api/auth/login", json={"login": "demo", "password": "demo"}
    )
    assert response.status_code in (200, 401, 403)


def test_auth_login_sets_cookie_and_me_route_returns_user():
    response = client.post(
        "/api/auth/login",
        json={"login": "demo", "password": "demo"},
    )

    assert response.status_code in (200, 401, 403)
    if response.status_code == 200:
        assert "sim112_session" in response.cookies
        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["login"] == "demo"


def test_users_collection_route_exists():
    response = client.get("/api/users")
    assert response.status_code in (200, 401)


def test_scenarios_route_exists():
    response = client.get("/api/scenarios")
    assert response.status_code == 200


def test_map_valid_returns_full_address(monkeypatch):
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "_fetch_yandex_geocoder",
        lambda api_key, query, kind=None: {
            "response": {
                "GeoObjectCollection": {
                    "featureMember": [
                        {
                            "GeoObject": {
                                "metaDataProperty": {
                                    "GeocoderMetaData": {
                                        "kind": "house",
                                        "Address": {
                                            "formatted": "Россия, Москва, Тверская улица, 7",
                                            "Components": [
                                                {
                                                    "kind": "district",
                                                    "name": "Центральный административный округ",
                                                }
                                            ],
                                        },
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        },
    )

    response = client.get("/api/map_valid", params={"type": "house"})

    assert response.status_code == 200
    assert response.json() == {
        "type": "house",
        "address": "Россия, Москва, Тверская улица, 7, Центральный административный округ",
        "okrug": "Центральный административный округ",
    }


def test_map_valid_generates_location_and_requests_house_kind(monkeypatch):
    monkeypatch.setenv("YANDEX_GEOCODER_API_KEY", "geocoder-key")

    def fake_geocoder(api_key, query, kind=None):
        assert api_key == "geocoder-key"
        assert kind == "house"
        longitude, latitude = map(float, query.split(","))
        assert 36.8 <= longitude <= 37.97
        assert 55.5 <= latitude <= 56.0
        return {
            "response": {
                "GeoObjectCollection": {
                    "featureMember": [
                        {
                            "GeoObject": {
                                "metaDataProperty": {
                                    "GeocoderMetaData": {
                                        "kind": "house",
                                        "Address": {
                                            "formatted": "Россия, Москва, Тверская улица, 7"
                                        },
                                    }
                                }
                            }
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(main, "_fetch_yandex_geocoder", fake_geocoder)

    response = client.get("/api/map_valid", params={"type": "house"})

    assert response.status_code == 200


def test_map_valid_returns_coordinates_for_water(monkeypatch):
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", "test-key")

    def fake_geocoder(api_key, query, kind=None):
        assert api_key == "test-key"
        assert query in main.MAP_FEATURE_QUERIES["water"]
        return {
            "response": {
                "GeoObjectCollection": {
                    "featureMember": [{"GeoObject": {"Point": {"pos": "37.61 55.75"}}}]
                }
            }
        }

    monkeypatch.setattr(main, "_fetch_yandex_geocoder", fake_geocoder)

    response = client.get("/api/map_valid", params={"type": "water"})

    assert response.status_code == 200
    assert response.json() == {
        "type": "water",
        "coordinates": {"latitude": 55.75, "longitude": 37.61},
    }


def test_map_valid_returns_coordinates_for_forest(monkeypatch):
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", "test-key")

    def fake_geocoder(api_key, query, kind=None):
        assert api_key == "test-key"
        assert query in main.MAP_FEATURE_QUERIES["forest"]
        return {
            "response": {
                "GeoObjectCollection": {
                    "featureMember": [{"GeoObject": {"Point": {"pos": "37.7 55.8"}}}]
                }
            }
        }

    monkeypatch.setattr(main, "_fetch_yandex_geocoder", fake_geocoder)

    response = client.get("/api/map_valid", params={"type": "forest"})

    assert response.status_code == 200
    assert response.json() == {
        "type": "forest",
        "coordinates": {"latitude": 55.8, "longitude": 37.7},
    }


def test_map_valid_supports_legacy_geocoder_key_for_all_types(monkeypatch):
    monkeypatch.delenv("YANDEX_GEOCODER_API_KEY", raising=False)
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", "legacy-key")

    def fake_geocoder(api_key, query, kind=None):
        assert api_key == "legacy-key"
        return {
            "response": {
                "GeoObjectCollection": {
                    "featureMember": [{"GeoObject": {"Point": {"pos": "37.61 55.75"}}}]
                }
            }
        }

    monkeypatch.setattr(main, "_fetch_yandex_geocoder", fake_geocoder)

    response = client.get("/api/map_valid", params={"type": "water"})

    assert response.status_code == 200


def test_map_valid_requires_yandex_key(monkeypatch):
    monkeypatch.delenv("YANDEX_GEOCODER_API_KEY", raising=False)
    monkeypatch.delenv("YANDEX_MAPS_API_KEY", raising=False)

    response = client.get("/api/map_valid", params={"type": "water"})

    assert response.status_code == 503
    assert "YANDEX_GEOCODER_API_KEY" in response.json()["detail"]


def test_map_valid_rejects_result_of_wrong_type(monkeypatch):
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", "test-key")
    monkeypatch.setattr(
        main,
        "_fetch_yandex_geocoder",
        lambda api_key, query, kind=None: {
            "response": {
                "GeoObjectCollection": {
                    "featureMember": [
                        {
                            "GeoObject": {
                                "metaDataProperty": {
                                    "GeocoderMetaData": {"kind": "street"}
                                },
                                "Point": {"pos": "37.61 55.75"},
                            }
                        }
                    ]
                }
            }
        },
    )

    response = client.get("/api/map_valid", params={"type": "street"})

    assert response.status_code == 404


def test_map_valid_reports_yandex_timeout_as_gateway_timeout(monkeypatch):
    monkeypatch.setenv("YANDEX_MAPS_API_KEY", "test-key")

    def timeout(url, timeout):
        raise URLError(TimeoutError("timed out"))

    monkeypatch.setattr(main, "urlopen", timeout)

    response = client.get("/api/map_valid", params={"type": "house"})

    assert response.status_code == 504
    assert response.json()["detail"] == "Таймаут соединения с Яндекс.Картами"


def test_frontend_deep_link_serves_index_html():
    response = client.get("/login")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")


def test_connection_websocket_route_exists():
    with client.websocket_connect("/api/connection/call") as websocket:
        welcome = websocket.receive_json()
        assert welcome["type"] == "ready"
        assert welcome["status"] == "connected"

        websocket.send_json({"type": "start", "session_id": "demo-session"})
        message = websocket.receive_json()
        assert message["type"] == "ack"
        assert message["status"] == "started"


def test_finish_session_uses_db_rubric_when_json_file_missing():
    initialize_database()
    with get_connection() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO rubrics (id, title, payload) VALUES (?, ?, ?)",
            (
                "rubric-db-only",
                "DB Only Rubric",
                json.dumps(
                    {
                        "id": "rubric-db-only",
                        "title": "DB Only Rubric",
                        "groups": [
                            {
                                "id": "g1",
                                "title": "Main",
                                "items": [
                                    {
                                        "id": "i1",
                                        "title": "Has form",
                                        "weight": 1.0,
                                        "field": "address",
                                        "check": "form",
                                    }
                                ],
                            }
                        ],
                        "critical": [],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
        connection.commit()

    response = client.post(
        "/api/sessions/finish",
        json={
            "scenario_id": "scn-001",
            "user_id": "u-001",
            "rubric_id": "rubric-db-only",
            "form": {"address": "Moscow"},
            "services": [],
            "messages": [],
            "answer_latency_sec": 10,
        },
    )

    assert response.status_code == 200
    assert response.json()["rubric_id"] == "rubric-db-only"
    assert response.json()["scores"]["i1"] == 100.0
