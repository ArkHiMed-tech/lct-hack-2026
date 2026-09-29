from fastapi import APIRouter, HTTPException, Query, status

from database import get_connection, initialize_database, seed_scenarios_from_json
from misc.card_generator import generate_card, validate_card_payload
from misc.crypto import dec_blob, dec_text, enc_blob, enc_text
from misc.incident_tree_api import (
    flag_guaranteed_services,
    get_leaf_by_code,
    informed_for_leaf,
    load_incident_graph,
    service_display_name,
    vis_class_for_leaf,
    vis_flags_from_tags,
)

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


def _backfill_scenario(payload: dict) -> dict:
    """Достройка старых сценариев на чтении (в БД не пишется):
    - vis_class из classifier_code + tags;
    - гарантии активных флагов в expected_services (исключённые не трогаем);
    - expected_services_informed из диспетчеризации, если поля нет вообще.
    Без classifier_code (статика scn-*, инфо-карточки) вычислить нечего.
    """
    expected = payload.get("expected") if isinstance(payload, dict) else None
    if not isinstance(expected, dict):
        return payload
    if not expected.get("classifier_code"):
        return payload
    try:
        graph = load_incident_graph()
        leaf = get_leaf_by_code(graph, expected["classifier_code"])
        if leaf is None:
            return payload
        tags = expected.get("tags") or {}
        flags = vis_flags_from_tags(tags)
        if not expected.get("vis_class"):
            vis = vis_class_for_leaf(graph, leaf, flags)
            expected["vis_class"] = vis["value"]
            expected["vis_class_fallback"] = vis["is_fallback"]
        excluded = set(expected.get("services_excluded") or [])
        services = expected.get("expected_services") or []
        for name in flag_guaranteed_services(graph, tags).values():
            if name not in services and name not in excluded:
                services.append(name)
        expected["expected_services"] = services
        if "expected_services_informed" not in expected:
            informed = informed_for_leaf(graph, leaf, flags)
            expected["expected_services_informed"] = [
                service_display_name(graph, gid) for gid in informed
            ]
    except Exception:
        return payload
    return payload


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
        payload = dec_blob(row["payload"])
        result.append(
            {
                "id": row["id"],
                "title": dec_text(row["title"]),
                "category": dec_text(row["category"]),
                "difficulty": dec_text(row["difficulty"]),
                "severity": dec_text(row["severity"]),
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
                        enc_text(report.get("what", "")),
                        enc_text(report.get("incident_category", "")),
                        enc_text(report.get("address", "")),
                        "",
                        enc_text(report.get("caller_name", "")),
                        enc_text(report.get("victims", "")),
                        "",
                        "",
                        enc_text(";".join(report.get("factors", []))),
                        "",
                        None,
                        enc_blob(report),
                    ),
                )
                report_id = cursor.lastrowid
                report_ids.append(report_id)
                for service in report.get("services", []):
                    cursor.execute(
                        "INSERT INTO dispatched_services (report_id, service_id) VALUES (?, ?)",
                        (report_id, enc_text(service)),
                    )
                row = cursor.execute(
                    "SELECT * FROM incident_reports WHERE id = ?", (report_id,)
                ).fetchone()
                from routers.reports import _build_scenario_from_report, _decrypt_report_row

                record = _decrypt_report_row(row)
                scenario = _build_scenario_from_report(
                    report_id, record, record.get("payload") or {}
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
                        enc_text(scenario["title"]),
                        enc_text(scenario["category"]),
                        enc_text(scenario["difficulty"]),
                        enc_text(scenario["severity"]),
                        enc_text(scenario["rubric_id"]),
                        scenario["sla_answer_sec"],
                        enc_blob(scenario),
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

    return _backfill_scenario(dec_blob(row["payload"]))

