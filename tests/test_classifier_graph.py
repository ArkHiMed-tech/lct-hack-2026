"""Тесты графа v2: классификатор из xlsx, совместимость v1, диспетчеризация."""
import json
from pathlib import Path

from misc.build_incident_graph import find_xlsx, parse_xlsx
from misc.card_generator import generate_card, validate_card_payload
from misc.incident_tree_api import (
    classifier_leaves,
    dispatch_for_leaf,
    leaves_for_root,
    load_incident_graph,
    match_leaf,
)

GRAPH_PATH = Path("misc/incident_graph.json")
V1_BACKUP = Path("/tmp/opencode/incident_graph.v1.json")


def test_parser_yields_509_unique_leaves():
    sections, leaves = parse_xlsx(find_xlsx())
    assert len(sections) == 23
    assert len(leaves) == 509
    codes = [leaf["code"] for leaf in leaves]
    assert len(set(codes)) == len(codes)
    assert all(leaf["path"] for leaf in leaves)
    filled = {leaf["g"] for leaf in leaves}
    assert filled == {1, 2, 3, 4, 5, 6, 7, 8, 9}


def test_v1_keys_unchanged():
    current = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    backup = json.loads(V1_BACKUP.read_text(encoding="utf-8"))
    for key in ("root", "root_children", "type_meta", "tag_sets", "children", "flow"):
        assert current[key] == backup[key], f"v1 key changed: {key}"


def test_classifier_section_shape():
    graph = load_incident_graph()
    classifier = graph["classifier"]
    assert classifier["leaf_count"] == 509
    assert len(classifier["sections"]) == 23
    assert len(classifier["services"]) == 62
    by_id = {s["id"]: s for s in classifier["services"]}
    assert by_id["mchs101"]["catalog"].startswith("Служба 101")
    assert by_id["smp"]["catalog"].startswith("Служба 103")
    assert by_id["cukb"]["catalog"] is None


def test_match_canonical_fire_leaf():
    graph = load_incident_graph()
    leaf = match_leaf(
        graph, where="Улица", detail="Мусор",
        sign="Открытое пламя / Дым", type_title="101",
    )
    assert leaf is not None
    assert leaf["code"] == "1010101"
    assert leaf["result"] == "пожар: мусор"
    assert leaf["dispatch"]["mchs101"] == "пожар: мусор"


def test_match_smell_leaf():
    graph = load_incident_graph()
    leaf = match_leaf(
        graph, where="Улица", detail="",
        sign="Запах гари", type_title="101",
    )
    assert leaf is not None
    assert leaf["code"] == "1011100"


def test_match_dtp_leaf():
    graph = load_incident_graph()
    leaf = match_leaf(
        graph, where="Транспорт", detail="Общественный транспорт",
        sign="Открытое пламя / Дым", type_title="ДТП",
    )
    assert leaf is not None
    assert leaf["code"] == "2010200"


def test_match_unknown_returns_none():
    graph = load_incident_graph()
    assert match_leaf(graph, where="Улица", detail="Мусор",
                       sign="Открытое пламя / Дым", type_title="Консультация") is None
    assert match_leaf(graph, where="Улица", detail="Тарелка супа",
                       sign="Открытое пламя / Дым", type_title="101") is None


def test_dispatch_flag_variants():
    graph = load_incident_graph()
    leaf = next(
        leaf for leaf in classifier_leaves(graph)
        if "mchs101_nd" in leaf["dispatch"] and "mchs101" in leaf["dispatch"]
    )
    base = dispatch_for_leaf(graph, leaf, {})
    assert base["mchs101"] == leaf["dispatch"]["mchs101"]
    flagged = dispatch_for_leaf(graph, leaf, {"nd": True})
    assert flagged["mchs101"] == leaf["dispatch"]["mchs101_nd"]


def test_dispatch_excludes_no_response():
    graph = load_incident_graph()
    leaf = next(
        leaf for leaf in classifier_leaves(graph)
        if leaf["dispatch"].get("smp_vict_absent") == "нет реагирования"
    )
    out = dispatch_for_leaf(graph, leaf, {"victims_absent": True})
    assert "smp" not in out


def test_leaves_for_root_coverage():
    graph = load_incident_graph()
    assert len(leaves_for_root(graph, "101")) == 271
    assert len(leaves_for_root(graph, "ДТП")) == 47
    assert leaves_for_root(graph, "Консультация") == []
    assert leaves_for_root(graph, "Нет такого типа") == []


def test_generated_classifier_codes_valid():
    graph = load_incident_graph()
    codes = {leaf["code"] for leaf in classifier_leaves(graph)}
    names = {
        (s["catalog"] or s["title"])
        for s in graph["classifier"]["services"]
    }
    for seed in range(100):
        payload = generate_card(seed=seed)["payload"]
        assert validate_card_payload(payload) == ""
        if payload.get("classifier_code"):
            assert payload["classifier_code"] in codes
            for service in payload["services"]:
                assert service in names, service
