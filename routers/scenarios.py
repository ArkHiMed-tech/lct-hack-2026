import json

from fastapi import APIRouter, HTTPException, Query, status

from database import get_connection, initialize_database, seed_scenarios_from_json
from misc.card_generator import generate_card, validate_card_payload

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


@router.get("/generate")
async def generate_scenarios(
    seed: int | None = Query(default=None),
    count: int = Query(default=1, ge=1, le=50),
    type: str | None = Query(default=None),
    publish: bool = Query(default=False),
    user_id: str | None = Query(default=None),
):
    """Генератор карточек обходом дерева классификатора.

    Обход: seed -> лист классификатора (Номер + Признак1→2→3) -> address ->
    caller -> victims -> services (диспетчеризация листа). Тип происшествия —
    Итоговый тип классификатора. Параметр type: Номер, точный Итоговый тип
    или подстрока. При publish=true сохраняет карточки в БД
    (incident_reports + dispatched_services) и публикует сценарии card-{id}.
    """
    import random as _random

    base_seed = seed if seed is not None else _random.SystemRandom().randint(0, 2**31 - 1)
    overrides = {"type": type} if type else None
    cards = []
    for i in range(count):
        try:
            item = generate_card(
                seed=base_seed + i, overrides=dict(overrides) if overrides else None
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            )
        payload = item["payload"]
        if user_id is not None:
            payload["user_id"] = user_id
        error = validate_card_payload(payload)
        if error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Generated invalid card (seed={base_seed + i}): {error}",
            )
        cards.append(item)

    scenario_ids: list[str] = []
    report_ids: list[int] = []
    if publish:
        from routers.reports import _build_scenario_from_report

        initialize_database()
        with get_connection() as connection:
            cursor = connection.cursor()
            for item in cards:
                report = item["payload"]
                cursor.execute(
                    """
                    INSERT INTO incident_reports (
                        user_id, scenario_id, what, incident_category, address, time,
                        caller_name, victims, conditions, threat, factors, actions, landmarks, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report.get("user_id"),
                        None,
                        report.get("what", ""),
                        report.get("incident_category", ""),
                        report.get("address", ""),
                        "",
                        report.get("caller_name", ""),
                        report.get("victims", ""),
                        "",
                        "",
                        ";".join(report.get("factors", [])),
                        "",
                        None,
                        json.dumps(report, ensure_ascii=False),
                    ),
                )
                report_id = cursor.lastrowid
                report_ids.append(report_id)
                for service in report.get("services", []):
                    cursor.execute(
                        "INSERT INTO dispatched_services (report_id, service_id) VALUES (?, ?)",
                        (report_id, service),
                    )
                row = cursor.execute(
                    "SELECT * FROM incident_reports WHERE id = ?", (report_id,)
                ).fetchone()
                scenario = _build_scenario_from_report(
                    report_id, dict(row), json.loads(dict(row).get("payload") or "{}")
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO scenarios (
                        id, title, category, difficulty, severity, rubric_id,
                        sla_answer_sec, payload, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        scenario["id"],
                        scenario["title"],
                        scenario["category"],
                        scenario["difficulty"],
                        scenario["severity"],
                        scenario["rubric_id"],
                        scenario["sla_answer_sec"],
                        json.dumps(scenario, ensure_ascii=False),
                    ),
                )
                scenario_ids.append(scenario["id"])
            connection.commit()

    return {
        "seed": base_seed,
        "count": len(cards),
        "cards": cards,
        "published": publish,
        "report_ids": report_ids,
        "scenario_ids": scenario_ids,
    }


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

