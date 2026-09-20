from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from database import get_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    login: str
    password: str


@router.post("/login")
async def login(payload: AuthRequest):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE login = ?",
            (payload.login,),
        ).fetchone()

    if row is None or row["password"] != payload.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    if row["active"] in (0, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь деактивирован",
        )

    user = dict(row)

    role_title = {
        "student": "Оператор ДДС",
        "teacher": "Преподаватель",
        "admin": "Администратор",
    }

    return {
        "id": user["id"],
        "login": user["login"],
        "name": user["name"],
        "last_name": user["last_name"],
        "role": user["role"],
        "post": role_title.get(user["role"], "Пользователь"),
        "group": user["group_name"],
        "active": bool(user["active"]),
    }
