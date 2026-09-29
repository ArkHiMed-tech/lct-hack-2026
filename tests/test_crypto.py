"""Шифрование БД: round-trip, HMAC-индекс, миграция, end-to-end через API."""
from fastapi.testclient import TestClient

from database import get_connection, initialize_database
from main import app
from misc.crypto import (
    dec_blob,
    dec_text,
    enc_blob,
    enc_text,
    is_encrypted,
    login_index,
)
from misc.migrate_db_crypto import migrate_connection

client = TestClient(app)


def test_text_roundtrip_and_envelope():
    token = enc_text("Иванова Мария +7 (903) 123-45-67")
    assert is_encrypted(token)
    assert dec_text(token) == "Иванова Мария +7 (903) 123-45-67"
    assert enc_text(token) == token  # идемпотентность
    assert dec_text("plain") == "plain"  # обратная совместимость
    assert dec_text(None) is None
    assert dec_text("") == ""
    assert enc_text("") == ""
    assert enc_text(None) is None


def test_blob_roundtrip():
    payload = {"what": "пожар: мусор", "services": ["Служба 101"], "n": 3}
    token = enc_blob(payload)
    assert is_encrypted(token)
    assert dec_blob(token) == payload


def test_login_index_deterministic():
    assert login_index("umc_operdds1") == login_index("umc_operdds1")
    assert login_index("umc_operdds1") != login_index("umc_operdds2")
    assert login_index("umc_operdds1").startswith("hmac1:")


def test_migrate_is_idempotent():
    initialize_database()
    with get_connection() as connection:
        second = migrate_connection(connection)
    assert second == {}


def test_login_with_seed_user_end_to_end():
    initialize_database()
    response = client.post(
        "/api/auth/login", json={"login": "umc_operdds1", "password": "dds112-1"}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["name"] == "Иванова Мария Петровна"
    assert body["role"] == "student"
    assert "sim112_session" in response.cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["name"] == "Иванова Мария Петровна"


def test_report_write_read_roundtrip_encrypted():
    what = "пожар: мусор ТЕСТ-ШИФР"
    created = client.post(
        "/api/reports/create",
        json={
            "user_id": "u-001",
            "what": what,
            "caller_name": "Тестов Тест Тестович",
            "address": "Москва, Тестовая улица, д. 1",
            "services": ["Служба 101 (тест)"],
        },
    )
    assert created.status_code == 200, created.text
    report_id = created.json()["report_id"]

    fetched = client.get(f"/api/reports/{report_id}")
    assert fetched.status_code == 200
    assert fetched.json()["what"] == what
    assert fetched.json()["services"] == ["Служба 101 (тест)"]

    # В БД — только шифротекст.
    with get_connection() as connection:
        row = connection.execute(
            "SELECT what, caller_name, payload FROM incident_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        assert what not in (row["what"] or "")
        assert "Тестов" not in (row["caller_name"] or "")
        assert what not in (row["payload"] or "")
        svc = connection.execute(
            "SELECT service_id FROM dispatched_services WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        assert "тест" not in (svc["service_id"] or "").lower()
