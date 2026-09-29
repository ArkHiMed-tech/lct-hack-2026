"""Миграция plaintext -> шифрованные значения (идемпотентная).

Зашифрованное определяется по envelope-префиксам (``enc1:``/``hmac1:``),
такие значения не трогаются. Запуск: ``python3 misc/migrate_db_crypto.py``
или автоматически в ``database.initialize_database()``.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from misc.crypto import enc_blob, enc_text, is_encrypted, is_login_index, login_index

# таблица -> (текстовые колонки, login-колонки, blob-колонки)
TABLE_FIELDS: dict[str, tuple[list[str], list[str], list[str]]] = {
    "users": (
        ["password", "email", "name", "last_name", "role", "group_name"],
        ["login"],
        [],
    ),
    "roles": (["title"], [], []),
    "scenarios": (
        ["title", "category", "difficulty", "severity", "rubric_id"],
        [],
        ["payload"],
    ),
    "rubrics": (["title"], [], ["payload"]),
    "incident_reports": (
        ["what", "incident_category", "address", "time", "caller_name",
         "victims", "conditions", "threat", "factors", "actions", "landmarks"],
        [],
        ["payload"],
    ),
    "dispatched_services": (["service_id"], [], []),
    "app_messages": (["sender", "text"], [], []),
    "results": (["verdict"], [], []),
}


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    ).fetchone()
    return row is not None


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_connection(connection: sqlite3.Connection) -> dict[str, int]:
    """Перешифровать все открытые значения. Возвращает {таблица: N_ячеек}."""
    counts: dict[str, int] = {}
    for table, (texts, logins, blobs) in TABLE_FIELDS.items():
        if not _table_exists(connection, table):
            continue
        existing = _columns(connection, table)
        cols = [c for c in texts + logins + blobs if c in existing]
        if not cols:
            continue
        updated = 0
        select_cols = ["rowid"] + cols
        for row in connection.execute(
            f"SELECT {', '.join(select_cols)} FROM {table}"
        ).fetchall():
            rowid = row[0]
            patch: dict[str, str] = {}
            for name, value in zip(cols, row[1:]):
                if value is None or value == "":
                    continue
                if name in logins:
                    if not is_login_index(value):
                        patch[name] = login_index(str(value))
                elif name in blobs:
                    if not is_encrypted(value):
                        patch[name] = enc_blob(str(value))
                else:
                    if not is_encrypted(value):
                        patch[name] = enc_text(str(value))
            if patch:
                connection.execute(
                    f"UPDATE {table} SET "
                    + ", ".join(f"{c} = ?" for c in patch)
                    + " WHERE rowid = ?",
                    (*patch.values(), rowid),
                )
                updated += len(patch)
        if updated:
            counts[table] = updated
    connection.commit()
    return counts


def main() -> int:
    from database import DB_PATH, get_connection, initialize_database

    initialize_database()
    with get_connection() as connection:
        counts = migrate_connection(connection)
    total = sum(counts.values())
    print(f"db: {DB_PATH}")
    for table, num in counts.items():
        print(f"  {table}: {num} ячеек зашифровано")
    print(f"итого: {total} ячеек")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
