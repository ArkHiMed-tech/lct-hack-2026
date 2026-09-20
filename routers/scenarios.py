import json

from fastapi import APIRouter, HTTPException, status

from database import get_connection, initialize_database, seed_scenarios_from_json

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("")
async def list_scenarios():
    initialize_database()
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, category, difficulty, severity, rubric_id, sla_answer_sec, payload FROM scenarios ORDER BY id"
        ).fetchall()

    if not rows:
        seed_scenarios_from_json()
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT id, title, category, difficulty, severity, rubric_id, sla_answer_sec, payload FROM scenarios ORDER BY id"
            ).fetchall()

    result = []
    for row in rows:
        payload = json.loads(row["payload"])
        result.append(
            {
                "id": row["id"],
                "title": row["title"],
                "category": row["category"],
                "difficulty": row["difficulty"],
                "severity": row["severity"],
                "estimate_sec": payload.get("sla_answer_sec", 240),
                "status": "done",
                "best_score": None,
                "summary": payload.get("expected", {}).get(
                    "address", payload.get("title", "")
                ),
            }
        )
    return result


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    initialize_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT payload FROM scenarios WHERE id = ?",
            (scenario_id,),
        ).fetchone()

    if row is None:
        seed_scenarios_from_json()
        with get_connection() as connection:
            row = connection.execute(
                "SELECT payload FROM scenarios WHERE id = ?",
                (scenario_id,),
            ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found"
        )

    return json.loads(row["payload"])
