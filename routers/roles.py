from fastapi import APIRouter
from database import get_connection
from misc.crypto import dec_text

router = APIRouter(prefix="/api", tags=["roles"])


@router.get("/roles")
async def list_roles():
    with get_connection() as connection:
        rows = connection.execute("SELECT id, title FROM roles ORDER BY id").fetchall()
    return [{"id": row["id"], "title": dec_text(row["title"])} for row in rows]
