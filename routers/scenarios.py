import json

from fastapi import APIRouter, HTTPException, status

from database import get_connection, initialize_database, seed_scenarios_from_json

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _summary_from_payload(payload: dict) -> str:
    expected = payload.get("expected", {}) or {}
    # Новый формат из карточек: готовая строка.
    if isinstance(expected.get("address_str"), str) and expected["address_str"].strip():
        return expected["address_str"]
    addr = expected.get("address", "")
    if isinstance(addr, str):
        return addr or payload.get("title", "")
    if isinstance(addr, dict):
        if isinstance(addr.get("raw"), str) and addr["raw"].strip():
            return addr["raw"]
        parts = [
            addr.get("subject") or addr.get("city") or "",
            addr.get("street") and f"ул. {addr['street']}" or "",
            addr.get("house") and f"д. {addr['house']}" or "",
        ]
        text = ", ".join(p for p in parts if p)
        return text or payload.get("title", "")
    return payload.get("title", "")


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
                "summary": _summary_from_payload(payload),
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


@router.get("/generate")
async def generate_scenarios():
    ...
    return {"message": "Scenarios generated"}
