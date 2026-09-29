from fastapi import APIRouter, HTTPException, status

from database import get_connection
from misc.crypto import dec_text, enc_text, hash_password, normalize_login
from models import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users():
    with get_connection() as connection:
        rows = connection.execute("SELECT id, name FROM users").fetchall()
    users = [{"id": row["id"], "name": dec_text(row["name"]) or ""} for row in rows]
    return sorted(users, key=lambda u: u["name"])


@router.post("/create")
async def create_user(user: User):
    login = normalize_login(user.login)
    if not login:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Логин не должен быть пустым",
        )
    with get_connection() as connection:
        user_id = login.replace(" ", "-") or user.email
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO users (
                id, login, password, email, name, last_name, role, group_name, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                login,
                hash_password(user.password),
                enc_text(user.email),
                enc_text(user.name),
                enc_text(user.last_name),
                enc_text(user.role),
                enc_text(user.group_name),
                int(user.active),
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM users WHERE login = ?",
            (login,),
        ).fetchone()
        if row is None:
            return {"message": f"User {user.login} created", "info": None}
        info = dict(row)
        info["password"] = "********" if info.get("password") else None
        for field in ("email", "name", "last_name", "role", "group_name"):
            info[field] = dec_text(info.get(field))
        return {"message": f"User {user.login} created", "info": info}


@router.put("/{user_id}")
async def update_user(user_id: str, payload: dict):
    allowed_fields = {"role", "group_name", "active", "name", "last_name", "email"}
    updates = {key: value for key, value in payload.items() if key in allowed_fields}

    if "password" in payload and payload["password"]:
        updates["password"] = hash_password(payload["password"])

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет валидных полей для обновления",
        )

    with get_connection() as connection:
        assignments = ", ".join(f"{field} = ?" for field in updates)
        values = [
            value if field == "active" else (
                value if field == "password" else enc_text(value)
            )
            for field, value in updates.items()
        ]
        values.append(user_id)
        connection.execute(
            f"UPDATE users SET {assignments} WHERE id = ?",
            values,
        )
        connection.commit()

    return {"id": user_id, "updated": True, "fields": list(updates.keys())}
