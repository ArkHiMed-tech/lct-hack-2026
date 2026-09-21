import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from database import get_connection, initialize_database
from routers._scoring import compute_result

router = APIRouter(prefix="/api/sessions", tags=["sessions"])
BASE_DIR = Path(__file__).resolve().parents[1]
RUBRICS_DIR = BASE_DIR / "frontend" / "public" / "data" / "rubrics"


def _load_rubric(rubric_id: str):
    initialize_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT payload FROM rubrics WHERE id = ?",
            (rubric_id,),
        ).fetchone()
    if row is not None:
        return json.loads(row["payload"])
    rubric_path = RUBRICS_DIR / f"{rubric_id}.json"
    if not rubric_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Rubric not found"
        )
    with rubric_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _load_scenario(scenario_id: str) -> dict:
    initialize_database()
    with get_connection() as connection:
        row = connection.execute(
            "SELECT payload FROM scenarios WHERE id = ?",
            (scenario_id,),
        ).fetchone()
    if row is not None and row["payload"]:
        return json.loads(row["payload"])
    scenario_path = BASE_DIR / "frontend" / "public" / "data" / "scenarios" / f"{scenario_id}.json"
    if scenario_path.exists():
        with scenario_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found"
    )


def _load_user(user_id: str | None) -> dict:
    if not user_id:
        return {}
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, last_name FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else {}


def _build_session(payload: dict, scenario: dict, *, finished: bool) -> dict:
    answer_latency = payload.get("answer_latency_sec")
    try:
        answer_latency = float(answer_latency) if answer_latency is not None else None
    except (TypeError, ValueError):
        answer_latency = None
    dispatched_at = payload.get("dispatched_at_ms")
    ended_at = payload.get("ended_at_ms")
    return {
        "messages": payload.get("messages", []),
        "form": payload.get("form", {}),
        "services": payload.get("services", []),
        "dispatched": dispatched_at is not None,
        "dispatchedAtMs": dispatched_at,
        "endedAtMs": ended_at,
        "callStartedAtMs": 1 if (finished and dispatched_at and ended_at) else None,
        "answerLatencySec": answer_latency,
        "call": (payload.get("call") or scenario.get("call") or {}),
    }


@router.post("/draft")
async def draft_session(payload: dict):
    """Черновой скоринг для живого прогресса (замена lib/scoring.js)."""
    scenario_id = payload.get("scenario_id")
    if not scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="scenario_id is required"
        )
    rubric_id = payload.get("rubric_id") or "rubric-112-base"
    scenario = payload.get("scenario") if isinstance(payload.get("scenario"), dict) else None
    if scenario is None:
        scenario = _load_scenario(scenario_id)
    rubric = _load_rubric(rubric_id)
    user = payload.get("user") if isinstance(payload.get("user"), dict) else None
    if user is None:
        user = _load_user(payload.get("user_id"))
    session = _build_session(payload, scenario, finished=False)
    return compute_result(session, scenario, rubric, user)


@router.post("/finish")
async def finish_session(payload: dict):
    initialize_database()
    scenario_id = payload.get("scenario_id")
    user_id = payload.get("user_id")
    if not scenario_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="scenario_id is required"
        )

    rubric_id = payload.get("rubric_id") or "rubric-112-base"
    scenario = _load_scenario(scenario_id)
    rubric = _load_rubric(rubric_id)
    user = _load_user(user_id)
    session = _build_session(payload, scenario, finished=True)

    result = compute_result(session, scenario, rubric, user)

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO results (user_id, scenario_id, report_id, total_score, verdict)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, scenario_id, None, result["total_score"], result["verdict"]),
        )
        connection.commit()
        session_id = cursor.lastrowid

    result["session_id"] = session_id
    return result
