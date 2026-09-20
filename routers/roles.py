from fastapi import APIRouter
from database import get_connection

router = APIRouter(prefix="/api", tags=["roles"])


@router.get("/roles")
async def list_roles():
    with get_connection() as connection:
        rows = connection.execute("SELECT id, title FROM roles ORDER BY id").fetchall()
    return [{"id": row["id"], "title": row["title"]} for row in rows]
