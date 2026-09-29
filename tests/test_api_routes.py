import json

from fastapi.testclient import TestClient

from database import get_connection, initialize_database
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


def test_connection_websocket_sends_real_tts_chunk():
    with client.websocket_connect("/api/connection/call") as websocket:
        websocket.receive_json()
        websocket.send_json({"type": "start", "session_id": "demo-session"})
        websocket.receive_json()

        websocket.send_json(
            {
                "type": "operator_text",
                "session_id": "demo-session",
                "text": "Привет, мир",
            }
        )

        messages = []
        for _ in range(20):
            try:
                messages.append(websocket.receive_json())
            except Exception:
                break

        tts_messages = [msg for msg in messages if msg.get("type") == "tts_chunk"]
        assert tts_messages, "Expected a tts_chunk message from websocket"
        assert tts_messages[0].get("audio")
        assert tts_messages[0].get("audio") != "stub-audio-chunk"


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
