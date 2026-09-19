from pathlib import Path
import sqlite3
import sys

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
if 'test' in sys.argv:
    DB_PATH = BASE_DIR / "test_db.db"
else:
    DB_PATH = BASE_DIR / "db.db"

app = FastAPI(title="LCT Hack 2026 API")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(str(DB_PATH))
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """)
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

        default_roles = [
            ("student", "Обучающийся"),
            ("teacher", "Преподаватель"),
            ("admin", "Администратор"),
        ]
        connection.executemany(
            "INSERT OR IGNORE INTO roles (id, title) VALUES (?, ?)",
            default_roles,
        )

        connection.commit()


app.on_event("startup")


async def startup_event() -> None:
    initialize_database()


class User(BaseModel):
    login: str
    password: str
    email: str
    name: str | None = None
    last_name: str | None = None
    role: str | None = None
    group_name: str | None = None
    active: bool = True


class IncidentReport(BaseModel):
    user_id: str | None = None
    scenario_id: str | None = None
    what: str = Field(default="")
    incident_category: str = Field(default="")
    address: str = Field(default="")
    time: str = Field(default="")
    caller_name: str = Field(default="")
    victims: str = Field(default="")
    conditions: str = Field(default="")
    threat: str = Field(default="")
    factors: list[str] = Field(default_factory=list)
    actions: str = Field(default="")
    landmarks: str | None = None
    services: list[str] = Field(default_factory=list)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "frontend_build_exists": FRONTEND_DIST.exists(),
        "database_exists": DB_PATH.exists(),
    }


@app.post("/api/users/create")
async def create_user(user: User):
    with get_connection() as connection:
        user_id = user.login.lower().replace(" ", "-") or user.email
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO users (
                id, login, password, email, name, last_name, role, group_name, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user.login,
                user.password,
                user.email,
                user.name,
                user.last_name,
                user.role,
                user.group_name,
                int(user.active),
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM users WHERE login = ?",
            (user.login,),
        ).fetchone()
        return {
            "message": f"User {user.login} created",
            "info": dict(row) if row else None,
        }


@app.post("/api/reports/create")
async def create_report(report: IncidentReport):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO incident_reports (
                user_id, scenario_id, what, incident_category, address, time,
                caller_name, victims, conditions, threat, factors, actions, landmarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.user_id,
                report.scenario_id,
                report.what,
                report.incident_category,
                report.address,
                report.time,
                report.caller_name,
                report.victims,
                report.conditions,
                report.threat,
                ";".join(report.factors),
                report.actions,
                report.landmarks,
            ),
        )
        report_id = cursor.lastrowid

        for service in report.services:
            cursor.execute(
                "INSERT INTO dispatched_services (report_id, service_id) VALUES (?, ?)",
                (report_id, service),
            )

        connection.commit()
        return {
            "message": "Incident report created",
            "report_id": report_id,
            "services": report.services,
        }


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
