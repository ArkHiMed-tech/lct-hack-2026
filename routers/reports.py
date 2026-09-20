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
                caller_name, victims, conditions, threat, factors, actions, landmarks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.get("user_id"),
                report.get("scenario_id"),
                report.get("what", ""),
                report.get("incident_category", ""),
                report.get("address", ""),
                report.get("time", ""),
                report.get("caller_name", ""),
                report.get("victims", ""),
                report.get("conditions", ""),
                report.get("threat", ""),
                ";".join(report.get("factors", [])),
                report.get("actions", ""),
                report.get("landmarks"),
            ),
        )
        report_id = cursor.lastrowid

        for service in report.get("services", []):
            cursor.execute(
                "INSERT INTO dispatched_services (report_id, service_id) VALUES (?, ?)",
                (report_id, service),
            )

        connection.commit()

    return {"message": "Incident report created", "report_id": report_id, "services": report.get("services", [])}


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
