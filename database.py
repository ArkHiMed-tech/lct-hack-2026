import json
import sqlite3
import sys
from pathlib import Path

from misc.crypto import enc_blob, enc_text, login_index
from misc.migrate_db_crypto import migrate_connection

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

if "test" in sys.argv:
    DB_PATH = BASE_DIR / "test_db.db"
else:
    DB_PATH = BASE_DIR / "db.db"


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

        if not _table_has_column(connection, "incident_reports", "payload"):
            connection.execute("ALTER TABLE incident_reports ADD COLUMN payload TEXT")

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
                    "u-001",
                    login_index("umc_operdds1"),
                    enc_text("dds112-1"),
                    enc_text("umc_operdds1@example.com"),
                    enc_text("Иванова Мария Петровна"),
                    enc_text("Иванова"),
                    enc_text("student"),
                    enc_text("Группа 1"),
                    1,
                ),
                (
                    "u-002",
                    login_index("umc_operdds2"),
                    enc_text("dds112-2"),
                    enc_text("umc_operdds2@example.com"),
                    enc_text("Смирнов Алексей Сергеевич"),
                    enc_text("Смирнов"),
                    enc_text("student"),
                    enc_text("Группа 1"),
                    1,
                ),
                (
                    "u-003",
                    login_index("umc_teacher"),
                    enc_text("teach112"),
                    enc_text("umc_teacher@example.com"),
                    enc_text("Кузнецов Никита Андреевич"),
                    enc_text("Кузнецов"),
                    enc_text("teacher"),
                    enc_text("Преподаватели"),
                    1,
                ),
                (
                    "u-004",
                    login_index("umc_admin"),
                    enc_text("admin112"),
                    enc_text("umc_admin@example.com"),
                    enc_text("Соколова Дарья Викторовна"),
                    enc_text("Соколова"),
                    enc_text("admin"),
                    enc_text("Администраторы"),
                    1,
                ),
            ],
        )

        connection.commit()
        # Шифрование at rest: добить plaintext предыдущих версий (идемпотентно).
        migrate_connection(connection)


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
