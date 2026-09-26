from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from database import get_connection

router = APIRouter(prefix="/api/auth", tags=["auth"])
SESSION_COOKIE_NAME = "sim112_session"


class AuthRequest(BaseModel):
    login: str
    password: str


def serialize_user(row: dict) -> dict:
    role_title = {
        "student": "Оператор ДДС",
        "teacher": "Преподаватель",
        "admin": "Администратор",
    }

    return {
        "id": row["id"],
        "login": row["login"],
        "name": row["name"],
        "last_name": row["last_name"],
        "role": row["role"],
        "post": role_title.get(row["role"], "Пользователь"),
        "group": row["group_name"],
        "active": bool(row["active"]),
    }


@router.post("/login")
async def login(payload: AuthRequest, response: Response):
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

    user = serialize_user(dict(row))
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=user["login"],
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return user


@router.get("/me")
async def me(request: Request):
    login = request.cookies.get(SESSION_COOKIE_NAME)
    if not login:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован",
        )

    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE login = ?",
            (login,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия не найдена",
        )

    if row["active"] in (0, False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь деактивирован",
        )

    return serialize_user(dict(row))


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"ok": True}
