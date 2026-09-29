import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from database import get_connection, initialize_database
from misc.crypto import enc_text

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
BASE_DIR = Path(__file__).resolve().parents[1]
RUBRICS_DIR = BASE_DIR / "frontend" / "public" / "data" / "rubrics"


def _load_rubric(rubric_id: str):
    rubric_path = RUBRICS_DIR / f"{rubric_id}.json"
    if not rubric_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rubric not found"
        )
    with rubric_path.open("r", encoding="utf-8") as file:
        return json.load(file)


@router.post("/finish")
async def finish_session(payload: dict):
    initialize_database()
    scenario_id = payload.get("scenario_id")
    user_id = payload.get("user_id")
    form = payload.get("form", {})
    services = payload.get("services", [])
    messages = payload.get("messages", [])
    answer_latency_sec = float(payload.get("answer_latency_sec", 0) or 0)

    rubric_id = payload.get("rubric_id") or "rubric-112-base"
    rubric = _load_rubric(rubric_id)

    scores = {}
    failed_items = []
    critical_failures = []
    total_score = 0.0

    for group in rubric["groups"]:
        for item in group["items"]:
            item_id = item["id"]
            weight = float(item.get("weight", 0.0))
            value = 0.0

            field = item.get("field")
            if item.get("check") == "form" and field:
                value = 1.0 if form.get(field) not in (None, "", []) else 0.0
            elif item.get("check") == "timing":
                value = (
                    1.0 if answer_latency_sec <= item.get("target_sec", 999) else 0.0
                )
            elif item.get("check") == "dispatch_before_end":
                value = 1.0 if services else 0.0
            elif item.get("check") == "service_match":
                value = 1.0 if bool(services) else 0.0
            elif item.get("check") == "text_any_operator":
                value = 1.0 if bool(messages) else 0.0
            elif item.get("check") == "form_complete":
                value = 1.0 if form else 0.0
            elif item.get("check") == "category_match":
                value = 1.0 if form.get("incident_category") else 0.0
            elif item.get("check") == "timestamps":
                value = (
                    1.0
                    if payload.get("dispatched_at_ms") and payload.get("ended_at_ms")
                    else 0.0
                )

            scores[item_id] = round(value * 100.0, 2)
            total_score += value * weight * 100.0

            if value < 0.5:
                failed_items.append(
                    {
                        "id": item_id,
                        "group": group["id"],
                        "title": item["title"],
                    }
                )
                if item_id in rubric.get("critical", []):
                    critical_failures.append(
                        {
                            "id": item_id,
                            "group": group["id"],
                            "title": item["title"],
                        }
                    )

    total_score = round(total_score, 2)
    verdict = (
        "excellent" if total_score >= 85 else "pass" if total_score >= 60 else "fail"
    )

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO results (user_id, scenario_id, report_id, total_score, verdict)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, scenario_id, None, total_score, enc_text(verdict)),
        )
        connection.commit()
        session_id = cursor.lastrowid

    return {
        "session_id": session_id,
        "scenario_id": scenario_id,
        "rubric_id": rubric_id,
        "groups_meta": {
            group["id"]: {"title": group["title"], "passed": True}
            for group in rubric["groups"]
        },
        "answer_latency_sec": answer_latency_sec,
        "messages": messages,
        "form": form,
        "dispatched_services": services,
        "scores": scores,
        "total_score": total_score,
        "verdict": verdict,
        "failed_items": failed_items,
        "critical_failures": critical_failures,
        "detail": "Результат рассчитан на сервере по рубрике и введённым данным",
    }
