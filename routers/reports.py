import json
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from database import get_connection
from misc.crypto import dec_blob, dec_text, enc_blob, enc_text

router = APIRouter(prefix="/api/reports", tags=["reports"])
BASE_DIR = Path(__file__).resolve().parents[1]

REPORT_TEXT_FIELDS = (
    "what", "incident_category", "address", "time", "caller_name",
    "victims", "conditions", "threat", "factors", "actions", "landmarks",
)


def _decrypt_report_row(row: dict) -> dict:
    """Расшифровка строк incident_reports на границе БД -> клиент."""
    record = dict(row)
    for field in REPORT_TEXT_FIELDS:
        record[field] = dec_text(record.get(field))
    if "payload" in record:
        try:
            blob = dec_blob(record.get("payload"))
            record["payload"] = blob
        except (json.JSONDecodeError, TypeError, ValueError):
            record["payload"] = {}
    return record


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
                enc_text(report.get("what", "")),
                enc_text(report.get("incident_category", "")),
                enc_text(
                    report.get("address", "")
                    if isinstance(report.get("address", ""), str)
                    else json.dumps(report.get("address", ""), ensure_ascii=False)
                ),
                enc_text(report.get("time", "")),
                enc_text(report.get("caller_name", "")),
                enc_text(report.get("victims", "")),
                enc_text(report.get("conditions", "")),
                enc_text(report.get("threat", "")),
                enc_text(";".join(report.get("factors", []))),
                enc_text(report.get("actions", "")),
                enc_text(report.get("landmarks")),
                enc_blob(report),
            ),
        )
        report_id = cursor.lastrowid

        for service in report.get("services", []):
            cursor.execute(
                "INSERT INTO dispatched_services (report_id, service_id) VALUES (?, ?)",
                (report_id, enc_text(service)),
            )

        connection.commit()

    return {"message": "Incident report created", "report_id": report_id, "services": report.get("services", []), "scenario_id": None}


CATEGORY_TO_SCENARIO = {"101": "fire", "102": "police", "103": "ambulance", "104": "gas"}

# Главная служба классификатора -> категория тренажёра.
# Коммунальные службы -> utility, транспортные -> dth (решение зафиксировано;
# рубрика знает только fire/medical/gas/dth — остальные категории нейтральны
# для скоринга, как раньше police/ambulance).
MAIN_TO_CATEGORY = {
    "MCHS": "fire", "Police": "police",
    "AMBULANCE": "ambulance", "MOSGAZ": "gas",
    "MOSLIFT": "utility", "MOEK": "utility", "OEK": "utility",
    "MOESK": "utility", "MOSVODOCANAL": "utility", "MOSVODOSTOK": "utility",
    "MOSCOLLECTOR": "utility", "GORMOST": "utility", "GKH": "utility",
    "METRO": "dth", "MZD": "dth", "MOSGORTRANS": "dth", "AUTOROADS": "dth",
    "MGTS": "utility",
}
# Раздел классификатора -> категория тренажёра (для main=None).
SECTION_TO_CATEGORY = {1: "fire", 2: "dth", 3: "fire", 4: "fire", 5: "fire",
                       6: "fire", 7: "fire", 8: "fire", 9: "fire",
                       10: "fire", 11: "fire", 12: "dth", 13: "gas",
                       14: "utility", 15: "police", 16: "dth", 17: "police",
                       18: "police", 19: "police", 20: "utility",
                       21: "utility", 22: "ambulance", 23: "fire", 24: "police"}


def _main_category(main: str | None) -> str:
    """Категория по Главной службе; составные ('METRO, MZD') — по первому
    известному токену."""
    for token in str(main or "").replace(",", " ").split():
        if token in MAIN_TO_CATEGORY:
            return MAIN_TO_CATEGORY[token]
    return ""


def _scenario_category(payload: dict, row: dict) -> tuple[str, str]:
    """(category, group_label): категория тренажёра + группа карточки.

    Новые карточки: Главная служба / раздел классификатора.
    Старые карточки: incident_category вида '101' (legacy-маппинг).
    """
    category = _main_category(payload.get("main_service"))
    if not category:
        section = payload.get("classifier_section") or {}
        category = SECTION_TO_CATEGORY.get(section.get("g"), "")
    group = str(payload.get("incident_category") or row.get("incident_category") or "")
    if not category:
        category = CATEGORY_TO_SCENARIO.get(
            group, group if group in ("fire", "police", "ambulance", "gas", "dth", "utility") else "fire"
        )
    section = payload.get("classifier_section") or {}
    group_label = group or section.get("title") or category
    return category, group_label


def _build_scenario_from_report(report_id: int, row: dict, payload: dict) -> dict:
    scenario_id = f"card-{report_id}"
    category, group_label = _scenario_category(payload, row)
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
            "incident_group": group_label,
            "classifier_code": payload.get("classifier_code"),
            "classifier_path": payload.get("classifier_path") or [],
            "main_service": payload.get("main_service"),
            "vis_class": payload.get("vis_class"),
            "vis_class_fallback": payload.get("vis_class_fallback", False),
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
        record = _decrypt_report_row(row)
    try:
        payload = record.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
    except (TypeError, ValueError):
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
                scenario["id"], enc_text(scenario["title"]), enc_text(scenario["category"]),
                enc_text(scenario["difficulty"]), enc_text(scenario["severity"]),
                enc_text(scenario["rubric_id"]),
                scenario["sla_answer_sec"], enc_blob(scenario),
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
    return [_decrypt_report_row(row) for row in rows]


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

    payload = _decrypt_report_row(report)
    payload["messages"] = [
        {
            "sender": dec_text(item["sender"]),
            "text": dec_text(item["text"]),
            "created_at": item["created_at"],
        }
        for item in messages
    ]
    payload["services"] = [dec_text(row["service_id"]) for row in services]
    return payload


@router.post("/{report_id}/messages")
async def add_message(report_id: int, payload: dict):
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO app_messages (report_id, sender, text) VALUES (?, ?, ?)",
            (report_id, enc_text(payload.get("sender", "user")), enc_text(payload.get("text", ""))),
        )
        connection.commit()
    return {"message": "Message saved", "report_id": report_id}
