from fastapi import APIRouter
from database import get_connection
from misc.crypto import dec_text

router = APIRouter(prefix="/api", tags=["results"])


@router.get("/results")
async def list_results(user_id: str | None = None):
    with get_connection() as connection:
        if user_id:
            rows = connection.execute(
                "SELECT id AS session_id, user_id, scenario_id, total_score AS score, verdict, created_at AS date FROM results WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT id AS session_id, user_id, scenario_id, total_score AS score, verdict, created_at AS date FROM results ORDER BY created_at DESC"
            ).fetchall()

    return [
        {
            "session_id": row["session_id"],
            "user_id": row["user_id"],
            "scenario_id": row["scenario_id"],
            "score": row["score"],
            "verdict": dec_text(row["verdict"]),
            "date": row["date"],
        }
        for row in rows
    ]
