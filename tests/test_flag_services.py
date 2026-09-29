"""Флаговые службы end-to-end на уровне данных.

Каждый флаг панели обязан: иметь гарантированную службу, чьё имя —
в SERVICE_CATALOG, совпадает с backend-каталогом графа (иначе задвоение
плашек) и маппится в ОТДЕЛЬНУЮ ячейку дока тренажёра (103 и ЦЭМП — разные
ячейки: раньше делили одну ambulance с подписью ЦЭМП).
Плюс: маркерные ячейки xlsx не попадают в выезд, сохранение/публикация
проносит набор служб целиком.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from main import app
from misc.incident_tree_api import (
    dispatch_for_leaf,
    get_leaf_by_code,
    informed_for_leaf,
    load_incident_graph,
    service_display_name,
)

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / "frontend" / "src"
LIB = FRONT / "lib"

client = TestClient(app)


def _parse_catalog():
    src = (LIB / "serviceCatalog.js").read_text(encoding="utf-8")
    consts = dict(re.findall(r"export const (SVC_\w+) =\s*'((?:[^'\\]|\\.)*)'", src))
    entries = re.findall(r"^  '((?:[^'\\]|\\.)*)',", src, re.M)
    dock_ids = dict(
        re.findall(r"\[(SVC_\w+)\]: '([a-z0-9]+)'", src.split("SERVICE_DOCK_ID")[1])
    )
    return consts, set(entries), dock_ids


def _parse_flags():
    src = (LIB / "incidentClassifier.js").read_text(encoding="utf-8")
    defs = re.findall(r"\{ key: '(\w+)', label:", src.split("FLAG_DEFS")[1])
    flag_block = src.split("FLAG_SERVICE")[1].split("};")[0]
    return defs, dict(re.findall(r"(\w+):\s*(SVC_\w+)", flag_block))


def _dock_cells():
    src = (FRONT / "components" / "DispatchPanel.jsx").read_text(encoding="utf-8")
    sim = (FRONT / "pages" / "Simulator.jsx").read_text(encoding="utf-8")
    order = re.findall(r"\{ id: '([a-z0-9]+)', dds:", src.split("DDS_ORDER")[1])
    dock_ids = re.findall(r"DOCK_IDS = \[(.*?)\]", sim, re.S)[0]
    dock_ids = re.findall(r"'([a-z0-9]+)'", dock_ids)
    return order, dock_ids


def test_every_flag_has_service_in_catalog_and_own_cell():
    consts, entries, dock_ids = _parse_catalog()
    defs, flagmap = _parse_flags()
    assert set(flagmap) == set(defs), f"флаги без гарантии: {set(defs) - set(flagmap)}"
    order, sim_dock = _dock_cells()
    for flag, svc in flagmap.items():
        assert svc in consts, flag
        assert consts[svc] in entries, f"{flag}: {svc} нет в SERVICE_CATALOG"
        cell = dock_ids.get(svc)
        assert cell, f"{flag}: {svc} не маппится в док"
        assert cell in sim_dock, f"{flag}: ячейка {cell} вне DOCK_IDS тренажёра"
        assert cell in order, f"{flag}: ячейки {cell} нет в DDS_ORDER"


def test_103_and_cemp_are_different_cells():
    _, _, dock_ids = _parse_catalog()
    assert dock_ids["SVC_103"] != dock_ids["SVC_CEMP"]
    order, _ = _dock_cells()
    assert dock_ids["SVC_103"] in order and dock_ids["SVC_CEMP"] in order


def test_flag_services_match_backend_catalogs():
    consts, _, _ = _parse_catalog()
    _, flagmap = _parse_flags()
    gid_of = {
        "SVC_101": "mchs101", "SVC_102": "mvd", "SVC_103": "smp",
        "SVC_104": "mosgaz", "SVC_CEMP": "cemp",
    }
    by_id = {s["id"]: s for s in load_incident_graph()["classifier"]["services"]}
    for flag, svc in flagmap.items():
        assert by_id[gid_of[svc]]["catalog"] == consts[svc], flag


def test_marker_cells_excluded_from_dispatch():
    graph = load_incident_graph()
    leaf = get_leaf_by_code(graph, "1010101")
    # cemp_med='карточка-112': ЦЭМП не выезжает при medical...
    assert "cemp" not in dispatch_for_leaf(graph, leaf, {"medical": True})
    # ...а уведомляется (голубая плашка).
    informed = informed_for_leaf(graph, leaf, {"medical": True})
    assert "cemp" in informed
    assert service_display_name(graph, "cemp") == "ЦЭМП"


def test_no_response_still_excluded_everywhere():
    graph = load_incident_graph()
    leaf = next(
        leaf for leaf in graph["classifier"]["leaves"]
        if (leaf.get("dispatch") or {}).get("smp_vict_absent") == "нет реагирования"
    )
    assert "smp" not in dispatch_for_leaf(graph, leaf, {"victims_absent": True})
    assert "smp" not in informed_for_leaf(graph, leaf, {"victims_absent": True})


def test_save_publish_keeps_all_flag_services():
    consts, _, _ = _parse_catalog()
    _, flagmap = _parse_flags()
    all_flag_services = [consts[svc] for svc in flagmap.values()]
    created = client.post(
        "/api/reports/create",
        json={
            "user_id": "u-001", "what": "тест флаговых служб",
            "caller_name": "Тест", "caller_status": "очевидец",
            "victims": "нет", "tags": {"medical": True, "violation": True, "gas": True},
            "services": all_flag_services, "services_informed": [],
        },
    )
    assert created.status_code == 200, created.text
    report_id = created.json()["report_id"]
    published = client.post(f"/api/reports/{report_id}/publish")
    scenario = client.get(f"/api/scenarios/{published.json()['scenario_id']}")
    assert scenario.status_code == 200
    expected = scenario.json()["expected"]
    for svc in all_flag_services:
        assert svc in expected["expected_services"], svc
