from fastapi import APIRouter, HTTPException, status

from database import get_connection, initialize_database, seed_rubrics_from_json
from misc.crypto import dec_blob

router = APIRouter(prefix="/api/rubrics", tags=["rubrics"])


@router.get("/{rubric_id}")
async def get_rubric(rubric_id: str):
    initialize_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT payload FROM rubrics WHERE id = ?",
            (rubric_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rubric not found"
        )

    return dec_blob(row["payload"])
