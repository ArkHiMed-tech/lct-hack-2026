import json
import sqlite3
import sys
from pathlib import Path

from misc.crypto import (
    dec_text,
    enc_blob,
    enc_text,
    hash_password,
    is_login_index,
    is_password_hash,
    normalize_login,
    password_matches,
)
from misc.migrate_db_crypto import migrate_connection

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

if "test" in sys.argv:
    DB_PATH = BASE_DIR / "test_db.db"
else:
    DB_PATH = BASE_DIR / "db.db"


# Сид-пользователи из коробки: логин — ОТКРЫТЫМ текстом, пароль — хэш PBKDF2.
# Именно по этим парам новый клиент логинится сразу после клона:
#   umc_operdds1 / dds112-1  (студент)
#   umc_operdds2 / dds112-2  (студент)
#   umc_teacher  / teach112   (преподаватель)
#   umc_admin    / admin112    (администратор)
SEED_USERS = [
    (
        "u-001", "umc_operdds1", "dds112-1", "umc_operdds1@example.com",
        "Иванова Мария Петровна", "Иванова", "student", "Группа 1", 1,
    ),
    (
        "u-002", "umc_operdds2", "dds112-2", "umc_operdds2@example.com",
        "Смирнов Алексей Сергеевич", "Смирнов", "student", "Группа 1", 1,
    ),
    (
        "u-003", "umc_teacher", "teach112", "umc_teacher@example.com",
        "Кузнецов Никита Андреевич", "Кузнецов", "teacher", "Преподаватели", 1,
    ),
    (
        "u-004", "umc_admin", "admin112", "umc_admin@example.com",
        "Соколова Дарья Викторовна", "Соколова", "admin", "Администраторы", 1,
    ),
]
# login -> пароль из сид-карты (нужен для восстановления пароля,
# если старая БД зашифрована чужим ключом и не расшифровывается).
SEED_PASSWORDS = {normalize_login(u[1]): u[2] for u in SEED_USERS}


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DB_PATH))
    connection.row_factory = sqlite3.Row
    return connection


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _table_has_column(
    connection: sqlite3.Connection, table_name: str, column_name: str
) -> bool:
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(column[1] == column_name for column in columns)


def _ensure_table_schema() -> None:
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL
            )
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                login TEXT UNIQUE,
                password TEXT,
                email TEXT,
                name TEXT,
                last_name TEXT,
                role TEXT,
                group_name TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT,
                difficulty TEXT,
                severity TEXT,
                rubric_id TEXT,
                sla_answer_sec INTEGER,
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)

        if not _table_has_column(connection, "scenarios", "payload"):
            connection.execute("ALTER TABLE scenarios ADD COLUMN payload TEXT")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS rubrics (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                payload TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)

        if not _table_has_column(connection, "rubrics", "payload"):
            connection.execute("ALTER TABLE rubrics ADD COLUMN payload TEXT")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS incident_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                scenario_id TEXT,
                what TEXT,
                incident_category TEXT,
                address TEXT,
                time TEXT,
                caller_name TEXT,
                victims TEXT,
                conditions TEXT,
                threat TEXT,
                factors TEXT,
                actions TEXT,
                landmarks TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            )
            """)

        if not _table_has_column(connection, "incident_reports", "payload"):
            connection.execute("ALTER TABLE incident_reports ADD COLUMN payload TEXT")

        connection.execute("""
            CREATE TABLE IF NOT EXISTS dispatched_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER NOT NULL,
                service_id TEXT NOT NULL,
                FOREIGN KEY (report_id) REFERENCES incident_reports(id)
            )
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER,
                sender TEXT,
                text TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (report_id) REFERENCES incident_reports(id)
            )
            """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                scenario_id TEXT,
                report_id INTEGER,
                total_score REAL,
                verdict TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id),
                FOREIGN KEY (report_id) REFERENCES incident_reports(id)
            )
            """)

        connection.executemany(
            "INSERT OR IGNORE INTO roles (id, title) VALUES (?, ?)",
            [
                ("student", "Обучающийся"),
                ("teacher", "Преподаватель"),
                ("admin", "Администратор"),
            ],
        )

        connection.executemany(
            """
            INSERT OR IGNORE INTO users (
                id, login, password, email, name, last_name, role, group_name, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    user_id,
                    normalize_login(login),
                    hash_password(password),
                    enc_text(email),
                    enc_text(name),
                    enc_text(last_name),
                    enc_text(role),
                    enc_text(group_name),
                    active,
                )
                for (
                    user_id, login, password, email, name,
                    last_name, role, group_name, active,
                ) in SEED_USERS
            ],
        )

        connection.commit()
        # Шифрование at rest: добить plaintext предыдущих версий (идемпотентно).
        # Логины НЕ шифруются (см. _repair_legacy_logins ниже).
        migrate_connection(connection)
        # Чиним старые БД: hmac-логины -> plaintext, пароли -> хэш.
        _repair_legacy_logins(connection)
        # Чужая БД (склонирована с другой машины без .dbkey): старые шифротексты
        # не расшифровать — чистим только нечитаемые данные, сидов чиним всегда.
        _rebuild_undecryptable_data(connection)
        _ensure_seed_users(connection)
        _seed_catalog_if_empty(connection)


def _decryptable(value) -> bool:
    """Проверка, что значение читается текущим ключом (или оно не шифровано)."""
    try:
        dec_text(value)
        return True
    except ValueError:
        return False


def _rebuild_undecryptable_data(connection: sqlite3.Connection) -> bool:
    """Самовосстановление после клона чужой БД без ключа.

    Если PII сид-пользователей не расшифровывается текущим ключом — значит,
    вся БД зашифрована чужим ключом. Такие строки нечитаемы и невосстановимы:
    чистим таблицы данных (users-ПДн сидов перезапишет _ensure_seed_users,
    сценарии/рубрики — _seed_catalog_if_empty). Отчёты/результаты чужой машины
    при этом удаляются — это честнее, чем 500-е на каждом чтении.
    Возвращает True, если была пересборка.
    """
    seed_ids = [user_id for user_id, *_ in SEED_USERS]
    placeholders = ",".join("?" for _ in seed_ids)
    broken = False
    for row in connection.execute(
        f"SELECT id, name, email FROM users WHERE id IN ({placeholders})", seed_ids
    ).fetchall():
        for field in ("name", "email"):
            if row[field] not in (None, "") and not _decryptable(row[field]):
                broken = True
                break
        if broken:
            break
    if not broken:
        return False
    print(
        "ВНИМАНИЕ: БД зашифрована другим ключом (клон без .dbkey). "
        "Нечитаемые данные будут пересозданы, сид-пользователи восстановлены."
    )
    for table in (
        "dispatched_services", "app_messages", "results", "incident_reports",
        "scenarios", "rubrics",
    ):
        try:
            connection.execute(f"DELETE FROM {table}")
        except Exception:
            pass
    # Кастомные пользователи с чужим шифром невосстановимы — удаляем,
    # сидов перезапишет _ensure_seed_users.
    connection.execute(
        f"DELETE FROM users WHERE id NOT IN ({placeholders})", seed_ids
    )
    for user_id in seed_ids:
        connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    return True


def _seed_catalog_if_empty(connection: sqlite3.Connection) -> None:
    """Досеять сценарии/рубрики из JSON, если таблицы пустые (свежая БД)."""
    try:
        scenarios_empty = connection.execute(
            "SELECT COUNT(*) AS n FROM scenarios"
        ).fetchone()["n"] == 0
        rubrics_empty = connection.execute(
            "SELECT COUNT(*) AS n FROM rubrics"
        ).fetchone()["n"] == 0
    except Exception:
        return
    if scenarios_empty or rubrics_empty:
        connection.commit()
        if scenarios_empty:
            seed_scenarios_from_json()
        if rubrics_empty:
            seed_rubrics_from_json()


def _repair_legacy_logins(connection: sqlite3.Connection) -> int:
    """Миграция со старых БД, где login хранился как ``hmac1:...``.

    HMAC необратим, поэтому такие строки нельзя «расшифровать» — их логины
    восстанавливаем по сид-карте через связку (id -> login). Возвращает число
    починенных строк. Кастомных пользователей с hmac-логином (не из сидов)
    не трогаем — их логины восстановить невозможно, но и ломать их нельзя.
    """
    seed_login_by_id = {user_id: normalize_login(login) for user_id, login, *_ in SEED_USERS}
    fixed = 0
    for row in connection.execute("SELECT id, login FROM users").fetchall():
        login = row["login"]
        if not is_login_index(login):
            continue
        plain = seed_login_by_id.get(row["id"])
        if plain is None:
            continue
        password = SEED_PASSWORDS.get(plain)
        connection.execute(
            "UPDATE users SET login = ?, password = ? WHERE id = ?",
            (plain, hash_password(password), row["id"]),
        )
        fixed += 1
    if fixed:
        connection.commit()
        print(f"users: восстановлено {fixed} legacy hmac-логинов в plaintext.")
    return fixed


def _ensure_seed_users(connection: sqlite3.Connection) -> int:
    """Гарантия входа из коробки.

    Если сид-пользователь отсутствует ИЛИ его пароль не проходит проверку
    сид-паролем (чужой .dbkey / битая БД с другой машины) — пересоздаём его
    с известными логином/паролем. Правим только 4 сид-строки (wipe чужих
    нечитаемых данных делает _rebuild_undecryptable_data выше).
    """
    restored = 0
    for (user_id, login, password, email, name, last_name, role, group_name, active) in SEED_USERS:
        plain = normalize_login(login)
        row = connection.execute(
            "SELECT * FROM users WHERE id = ? OR login = ?", (user_id, plain)
        ).fetchone()
        if row is not None and password_matches(password, row["password"]):
            if not is_password_hash(row["password"]):
                # Плавный апгрейд legacy enc/plaintext пароля до хэша.
                connection.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (hash_password(password), row["id"]),
                )
                restored += 1
            continue
        connection.execute(
            """
            INSERT OR REPLACE INTO users (
                id, login, password, email, name, last_name, role, group_name, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id, plain, hash_password(password),
                enc_text(email), enc_text(name), enc_text(last_name),
                enc_text(role), enc_text(group_name), active,
            ),
        )
        restored += 1
    if restored:
        connection.commit()
        print(f"users: восстановлено {restored} сид-пользователей (вход из коробки).")
    return restored


def seed_scenarios_from_json() -> None:
    scenarios_dir = FRONTEND_DIR / "public" / "data" / "scenarios"
    if not scenarios_dir.exists():
        return

    catalog = _load_json(scenarios_dir / "catalog.json")
    for item in catalog:
        scenario_id = item["id"]
        scenario_path = scenarios_dir / f"{scenario_id}.json"
        if not scenario_path.exists():
            continue
        payload = _load_json(scenario_path)
        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO scenarios (
                    id, title, category, difficulty, severity, rubric_id,
                    sla_answer_sec, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    payload["id"],
                    enc_text(payload["title"]),
                    enc_text(payload["category"]),
                    enc_text(payload["difficulty"]),
                    enc_text(payload["severity"]),
                    enc_text(payload.get("rubric_id")),
                    payload.get("sla_answer_sec"),
                    enc_blob(payload),
                ),
            )
            connection.commit()


def seed_rubrics_from_json() -> None:
    rubrics_dir = FRONTEND_DIR / "public" / "data" / "rubrics"
    if not rubrics_dir.exists():
        return

    for rubric_file in rubrics_dir.glob("*.json"):
        payload = _load_json(rubric_file)
        with get_connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO rubrics (id, title, payload, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (
                    payload["id"],
                    enc_text(payload["title"]),
                    enc_blob(payload),
                ),
            )
            connection.commit()


def initialize_database() -> None:
    _ensure_table_schema()


def initialize_dev_data() -> None:
    initialize_database()
    seed_scenarios_from_json()
    seed_rubrics_from_json()
