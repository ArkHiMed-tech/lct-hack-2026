from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel

from database import get_connection
from misc.crypto import (
    dec_text,
    hash_password,
    is_password_hash,
    normalize_login,
    password_matches,
)

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
        "name": dec_text(row["name"]),
        "last_name": dec_text(row["last_name"]),
        "role": dec_text(row["role"]),
        "post": role_title.get(dec_text(row["role"]), "Пользователь"),
        "group": dec_text(row["group_name"]),
        "active": bool(row["active"]),
    }


def _find_user(connection, login: str):
    """Поиск по нормализованному plaintext-логину (регистр не важен)."""
    return connection.execute(
        "SELECT * FROM users WHERE login = ?",
        (normalize_login(login),),
    ).fetchone()


@router.post("/login")
async def login(payload: AuthRequest, response: Response):
    with get_connection() as connection:
        row = _find_user(connection, payload.login)

        if row is None or not password_matches(payload.password, row["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверный логин или пароль",
            )

        if row["active"] in (0, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Пользователь деактивирован",
            )

        # Плавный апгрейд legacy enc/plaintext пароля до хэша при успешном входе.
        if not is_password_hash(row["password"]):
            connection.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (hash_password(payload.password), row["id"]),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (row["id"],)
            ).fetchone()

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
        row = _find_user(connection, login)

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
