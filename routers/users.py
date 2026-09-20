from fastapi import APIRouter, HTTPException, status

from database import get_connection
from models import User

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name FROM users ORDER BY name"
        ).fetchall()
    return [{"id": row["id"], "name": row["name"]} for row in rows]


@router.post("/create")
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


@router.put("/{user_id}")
async def update_user(user_id: str, payload: dict):
    allowed_fields = {"role", "group_name", "active", "name", "last_name", "email"}
    updates = {key: value for key, value in payload.items() if key in allowed_fields}

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет валидных полей для обновления",
        )

    with get_connection() as connection:
        assignments = ", ".join(f"{field} = ?" for field in updates)
        values = list(updates.values())
        values.append(user_id)
        connection.execute(
            f"UPDATE users SET {assignments} WHERE id = ?",
            values,
        )
        connection.commit()

    return {"id": user_id, "updated": True, "fields": list(updates.keys())}
