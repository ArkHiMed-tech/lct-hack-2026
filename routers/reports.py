import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from database import get_connection

router = APIRouter(prefix="/api/reports", tags=["reports"])
BASE_DIR = Path(__file__).resolve().parents[1]


@router.post("/create")
async def create_report(report: dict):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO incident_reports (
                user_id, scenario_id, what, incident_category, address, time,
                caller_name, victims, conditions, threat, factors, actions, landmarks, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.get("user_id"),
                report.get("scenario_id"),
                report.get("what", ""),
                report.get("incident_category", ""),
                report.get("address", "")
                if isinstance(report.get("address", ""), str)
                else json.dumps(report.get("address", ""), ensure_ascii=False),
                report.get("time", ""),
                report.get("caller_name", ""),
                report.get("victims", ""),
                report.get("conditions", ""),
                report.get("threat", ""),
                ";".join(report.get("factors", [])),
                report.get("actions", ""),
                report.get("landmarks"),
                json.dumps(report, ensure_ascii=False),
            ),
        )
        report_id = cursor.lastrowid

        for service in report.get("services", []):
            cursor.execute(
                "INSERT INTO dispatched_services (report_id, service_id) VALUES (?, ?)",
                (report_id, service),
            )

        connection.commit()

    return {"message": "Incident report created", "report_id": report_id, "services": report.get("services", []), "scenario_id": None}


CATEGORY_TO_SCENARIO = {"101": "fire", "102": "police", "103": "ambulance", "104": "gas"}


def _build_scenario_from_report(report_id: int, row: dict, payload: dict) -> dict:
    scenario_id = f"card-{report_id}"
    group = str(payload.get("incident_category") or row.get("incident_category") or "101")
    category = CATEGORY_TO_SCENARIO.get(group, group if group in ("fire", "police", "ambulance", "gas") else "fire")
    what = payload.get("what") or row.get("what") or "Происшествие"
    address_obj = payload.get("address_obj") or {}
    address_str = payload.get("address") or row.get("address") or ""
    factors = payload.get("factors") or []
    if isinstance(factors, str):
        factors = [factors]
    services = payload.get("services") or []
    description = (payload.get("description") or "").strip() or what
    caller = payload.get("caller_name") or row.get("caller_name") or ""
    created = row.get("created_at") or ""
    services_line = ", ".join(services) if services else "назначаются диспетчером"
    return {
        "id": scenario_id,
        "title": what,
        "category": category,
        "difficulty": "medium",
        "severity": "medium",
        "rubric_id": "rubric-112-base",
        "sla_answer_sec": 8,
        "from_card": True,
        "report_id": report_id,
        "call": {"phone": "", "caller_name_known": bool(caller), "address_auto": {"known": False}},
        "expected": {
            "incident_category": category,
            "incident_group": group,
            "incident_kind": payload.get("incident_kind"),
            "expected_services": services,
            "address": address_obj if isinstance(address_obj, dict) and address_obj else {"raw": address_str},
            "address_str": address_str,
            "factors": factors,
            "tags": payload.get("tags") or {},
            "caller_name": caller,
            "description": description,
        },
        "required_fields": ["what", "incident_category", "address", "caller_name", "factors"],
        "timeline": [
            {"seq": 1, "t_sec": 0, "speaker": "citizen", "emotion": None, "text": description},
            {
                "seq": 2, "t_sec": 30, "speaker": "system", "emotion": None,
                "text": f"Карточка №{report_id} ({created}): {what}. Службы: {services_line}.",
            },
        ],
        "quick_replies": [
            {"label": "Уточнить адрес", "text": "Назовите, пожалуйста, точный адрес: город, улица, дом, квартира и подъезд."},
            {"label": "Кто пострадал?", "text": "Скажите, есть ли пострадавшие и нужна ли медицинская помощь?"},
            {"label": "Службы едут", "text": "Службы уже направлены, оставайтесь на связи!"},
        ],
    }


@router.post("/{report_id}/publish")
async def publish_report(report_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM incident_reports WHERE id = ?", (report_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        record = dict(row)
    try:
        payload = json.loads(record.get("payload") or "{}")
    except (json.JSONDecodeError, TypeError):
        payload = {}
    scenario = _build_scenario_from_report(report_id, record, payload)
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO scenarios (
                id, title, category, difficulty, severity, rubric_id,
                sla_answer_sec, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                scenario["id"], scenario["title"], scenario["category"],
                scenario["difficulty"], scenario["severity"], scenario["rubric_id"],
                scenario["sla_answer_sec"], json.dumps(scenario, ensure_ascii=False),
            ),
        )
        connection.commit()
    return {"message": "Incident published", "report_id": report_id, "scenario_id": scenario["id"]}


@router.get("")
async def list_reports(user_id: str | None = None):
    with get_connection() as connection:
        if user_id:
            rows = connection.execute(
                "SELECT * FROM incident_reports WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM incident_reports ORDER BY created_at DESC"
            ).fetchall()
    return [dict(row) for row in rows]


@router.get("/{report_id}")
async def get_report(report_id: int):
    with get_connection() as connection:
        report = connection.execute(
            "SELECT * FROM incident_reports WHERE id = ?",
            (report_id,),
        ).fetchone()
        if report is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        messages = connection.execute(
            "SELECT sender, text, created_at FROM app_messages WHERE report_id = ? ORDER BY created_at",
            (report_id,),
        ).fetchall()
        services = connection.execute(
            "SELECT service_id FROM dispatched_services WHERE report_id = ?",
            (report_id,),
        ).fetchall()

    payload = dict(report)
    payload["messages"] = [dict(item) for item in messages]
    payload["services"] = [row["service_id"] for row in services]
    return payload


@router.post("/{report_id}/messages")
async def add_message(report_id: int, payload: dict):
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO app_messages (report_id, sender, text) VALUES (?, ?, ?)",
            (report_id, payload.get("sender", "user"), payload.get("text", "")),
        )
        connection.commit()
    return {"message": "Message saved", "report_id": report_id}
