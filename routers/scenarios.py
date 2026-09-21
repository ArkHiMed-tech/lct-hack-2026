import json

from fastapi import APIRouter, HTTPException, status

from database import get_connection, initialize_database, seed_scenarios_from_json

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("")
async def list_scenarios():
    from pathlib import Path

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

    catalog_path = Path(__file__).resolve().parents[1] / "frontend" / "public" / "data" / "scenarios" / "catalog.json"
    catalog_by_id: dict = {}
    if catalog_path.exists():
        try:
            with catalog_path.open("r", encoding="utf-8") as file:
                for item in json.load(file):
                    catalog_by_id[item["id"]] = item
        except (OSError, ValueError):
            catalog_by_id = {}

    with get_connection() as connection:
        best_rows = connection.execute(
            "SELECT scenario_id, MAX(total_score) AS best FROM results GROUP BY scenario_id"
        ).fetchall()
    best_by_scenario = {row["scenario_id"]: row["best"] for row in best_rows}

    result = []
    for row in rows:
        try:
            payload = json.loads(row["payload"]) if row["payload"] else {}
        except (TypeError, ValueError):
            payload = {}
        catalog = catalog_by_id.get(row["id"], {})
        expected = payload.get("expected", {}) or {}
        summary = catalog.get("summary") or payload.get("summary") or payload.get("title", "")
        best = best_by_scenario.get(row["id"])
        result.append(
            {
                "id": row["id"],
                "title": row["title"],
                "category": row["category"],
                "difficulty": row["difficulty"],
                "severity": row["severity"],
                "estimate_sec": catalog.get("estimate_sec", payload.get("estimate_sec", 240)),
                "status": "done" if best is not None else catalog.get("status", "new"),
                "best_score": best,
                "summary": summary,
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
