"""Шифрование БД: round-trip, plaintext-логины, хэши паролей, end-to-end через API."""
from fastapi.testclient import TestClient

from database import get_connection, initialize_database
from main import app
from misc.crypto import (
    dec_blob,
    dec_text,
    enc_blob,
    enc_text,
    hash_password,
    is_encrypted,
    is_password_hash,
    login_index,
    normalize_login,
    password_matches,
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


def test_logins_are_plaintext_and_normalized():
    # Логины НЕ шифруются: хранятся открытым текстом, регистр не важен.
    assert normalize_login("  Umc_OperDDS1 ") == "umc_operdds1"
    assert normalize_login("umc_operdds1") == "umc_operdds1"


def test_password_hash_and_legacy_matches():
    hashed = hash_password("dds112-1")
    assert is_password_hash(hashed)
    assert hash_password(hashed) == hashed  # идемпотентность
    assert password_matches("dds112-1", hashed)
    assert not password_matches("wrong", hashed)
    # Legacy-форматы тоже проходят (миграция со старых БД).
    assert password_matches("dds112-1", "dds112-1")
    assert password_matches("dds112-1", enc_text("dds112-1"))
    assert not password_matches("dds112-1", enc_text("other"))


def test_legacy_login_index_kept_for_migration_only():
    # Старый HMAC-индекс оставлен только для чтения/миграции старых БД.
    assert login_index("umc_operdds1") == login_index("umc_operdds1")
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
    assert body["login"] == "umc_operdds1"  # plaintext, не hmac1:...
    assert "hmac" not in body["login"]
    assert body["name"] == "Иванова Мария Петровна"
    assert body["role"] == "student"
    assert "sim112_session" in response.cookies
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["name"] == "Иванова Мария Петровна"
    assert me.json()["login"] == "umc_operdds1"


def test_login_is_case_insensitive():
    initialize_database()
    response = client.post(
        "/api/auth/login", json={"login": "UMC_OperDDS1", "password": "dds112-1"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["login"] == "umc_operdds1"


def test_wrong_password_rejected():
    initialize_database()
    response = client.post(
        "/api/auth/login", json={"login": "umc_operdds1", "password": "wrong"}
    )
    assert response.status_code == 401


def test_legacy_hmac_db_is_repaired_on_init():
    # Старая БД с hmac-логинами чинится при initialize_database,
    # вход по старому логину+паролю работает.
    from database import _repair_legacy_logins  # noqa: F401
    from misc.crypto import enc_text as _enc

    initialize_database()
    with get_connection() as connection:
        connection.execute(
            "UPDATE users SET login = ?, password = ? WHERE id = 'u-001'",
            (login_index("umc_operdds1"), _enc("dds112-1")),
        )
        connection.commit()
    initialize_database()  # должен починить hmac -> plaintext
    with get_connection() as connection:
        row = connection.execute(
            "SELECT login FROM users WHERE id = 'u-001'"
        ).fetchone()
        assert row["login"] == "umc_operdds1"
    response = client.post(
        "/api/auth/login", json={"login": "umc_operdds1", "password": "dds112-1"}
    )
    assert response.status_code == 200, response.text


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


def test_scenario_backfills_vis_class_and_services():
    from routers.scenarios import _backfill_scenario

    # Старая карточка без vis_class (как Обрушение ЛЭП 5190000): вычисляется.
    payload = {
        "expected": {
            "classifier_code": "5190000",
            "tags": {"evac": True, "tagDesc": "со слов заявителя"},
        }
    }
    out = _backfill_scenario(payload)
    assert out["expected"]["vis_class"] == "Обрушение конструкций"
    assert out["expected"]["vis_class_fallback"] is False

    # Существующее значение не перезаписывается.
    payload = {"expected": {"classifier_code": "5190000", "vis_class": "X"}}
    assert _backfill_scenario(payload)["expected"]["vis_class"] == "X"

    # Без classifier_code (статика scn-*, инфо-карточки) — нечего вычислять.
    payload = {"expected": {"classifier_code": None}}
    assert "vis_class" not in _backfill_scenario(payload)["expected"]
    assert _backfill_scenario({}) == {}


def test_backfill_adds_flag_guarantees_and_informed():
    from routers.scenarios import _backfill_scenario

    svc103 = (
        "Служба 103 (ГБУ города Москвы Станция скорой и неотложной "
        "медицинской помощи им.А.С. Пучкова)"
    )
    # Старый сценарий: флаг medical, пустые службы — гарантия достраивается.
    payload = {
        "expected": {
            "classifier_code": "1010101",
            "tags": {"medical": True},
            "expected_services": [],
        }
    }
    out = _backfill_scenario(payload)["expected"]
    assert svc103 in out["expected_services"]
    assert isinstance(out["expected_services_informed"], list)
    assert "ЦЭМП" in out["expected_services_informed"]

    # Явно исключённая служба не воскрешается backfill'ом.
    payload = {
        "expected": {
            "classifier_code": "1010101",
            "tags": {"medical": True},
            "expected_services": [],
            "services_excluded": [svc103],
        }
    }
    out = _backfill_scenario(payload)["expected"]
    assert svc103 not in out["expected_services"]


def test_publish_enforces_flag_guarantees():
    svc103 = (
        "Служба 103 (ГБУ города Москвы Станция скорой и неотложной "
        "медицинской помощи им.А.С. Пучкова)"
    )
    # Фронт прислал флаг, но не службу — publish обязан достроить.
    created = client.post(
        "/api/reports/create",
        json={
            "user_id": "u-001", "what": "тест гарантий",
            "caller_name": "Тест", "caller_status": "очевидец",
            "victims": "нет", "tags": {"medical": True},
            "services": [], "services_informed": [],
        },
    )
    assert created.status_code == 200, created.text
    published = client.post(f"/api/reports/{created.json()['report_id']}/publish")
    scenario = client.get(f"/api/scenarios/{published.json()['scenario_id']}")
    assert svc103 in scenario.json()["expected"]["expected_services"]


def test_informed_services_survive_publish():
    created = client.post(
        "/api/reports/create",
        json={
            "user_id": "u-001", "what": "тест информирования",
            "caller_name": "Тест", "caller_status": "очевидец",
            "victims": "нет", "services": ["ЦЭМП"],
            "services_informed": ["Аппарат МЭРА", "Метро"],
        },
    )
    assert created.status_code == 200, created.text
    report_id = created.json()["report_id"]
    published = client.post(f"/api/reports/{report_id}/publish")
    assert published.status_code == 200
    scenario = client.get(f"/api/scenarios/{published.json()['scenario_id']}")
    assert scenario.status_code == 200
    expected = scenario.json()["expected"]
    assert expected["expected_services"] == ["ЦЭМП"]
    assert expected["expected_services_informed"] == ["Аппарат МЭРА", "Метро"]
