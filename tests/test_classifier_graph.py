"""Тесты графа v2: классификатор из xlsx, совместимость v1, диспетчеризация."""
import json
from pathlib import Path

from misc.build_incident_graph import find_xlsx, parse_xlsx
from misc.card_generator import generate_card, validate_card_payload
from misc.incident_tree_api import (
    classifier_leaves,
    dispatch_for_leaf,
    get_tree_children,
    leaves_for_root,
    load_incident_graph,
    match_leaf,
    tree_path_for_code,
)

GRAPH_PATH = Path("misc/incident_graph.json")


def test_parser_yields_509_unique_leaves():
    sections, leaves = parse_xlsx(find_xlsx())
    assert len(sections) == 23
    assert len(leaves) == 509
    codes = [leaf["code"] for leaf in leaves]
    assert len(set(codes)) == len(codes)
    assert all(leaf["path"] for leaf in leaves)
    filled = {leaf["g"] for leaf in leaves}
    assert filled == {1, 2, 3, 4, 5, 6, 7, 8, 9}


def test_graph_v3_shape_no_legacy_keys():
    current = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    assert current["version"] == 3
    for key in ("root", "root_children", "type_meta", "tag_sets", "children", "flow"):
        assert key not in current, f"legacy key remains: {key}"
    classifier = current["classifier"]
    assert classifier["leaf_count"] == 509
    assert len(classifier["tree"]) == 9  # только заполненные разделы


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


def _walk_all_leaves(tree):
    """Все коды листьев, достижимые из дерева (g, путь)."""
    found = []

    def visit(node, prefix):
        for code in node.get("leaves", []) or []:
            found.append((code, prefix))
        for child in node.get("children", []) or []:
            visit(child, prefix + [child["value"]])

    for root in tree:
        visit(root, [])
    return found


def test_tree_covers_all_visible_leaves_exactly_once():
    graph = load_incident_graph()
    tree = graph["classifier"]["tree"]
    assert [r["g"] for r in tree] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    reached = _walk_all_leaves(tree)
    codes = [c for c, _ in reached]
    visible = {leaf["code"] for leaf in classifier_leaves(graph, visible_only=True)}
    assert set(codes) == visible
    assert len(set(codes)) == len(codes)
    by_code = {leaf["code"]: leaf for leaf in classifier_leaves(graph)}
    for code, prefix in reached:
        assert by_code[code]["path"] == prefix, code


def test_tree_has_no_hidden_branches():
    graph = load_incident_graph()

    def values(node):
        out = [node.get("value", "")]
        for child in node.get("children", []) or []:
            out += values(child)
        return out

    for root in graph["classifier"]["tree"]:
        assert "Не отображается оператору 112" not in values(root)


def test_cascade_fire_path():
    graph = load_incident_graph()
    step0 = get_tree_children(graph)
    assert [b["g"] for b in step0["buttons"]] == [1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert step0["selectable"] == []
    step1 = get_tree_children(graph, g=1)
    assert [b["value"] for b in step1["buttons"]] == [
        "на улице", "транспорт", "метро", "МЦК", "жилой дом", "объект",
    ]
    step2 = get_tree_children(graph, g=1, p1="на улице", p2="мусор")
    assert [b["value"] for b in step2["buttons"]] == ["открытое пламя", "дым"]
    assert step2["selectable"] == []
    step3 = get_tree_children(graph, g=1, p1="на улице", p2="мусор", p3="открытое пламя")
    assert step3["buttons"] == []
    assert step3["selectable"] == [{"code": "1010101", "result": "пожар: мусор"}]


def test_cascade_leaf_with_children_and_sections_separated():
    graph = load_incident_graph()
    dtp = get_tree_children(graph, g=2, p1="ДТП", p2="Транспорт служебный")
    assert dtp["selectable"] == [
        {"code": "2010300", "result": "ДТП без пострадавших - служебный"}
    ]
    assert [b["value"] for b in dtp["buttons"]] == ["104"]
    g4 = get_tree_children(graph, g=4)
    g5 = get_tree_children(graph, g=5)
    assert g4["buttons"] != g5["buttons"]
    assert tree_path_for_code(graph, "1010101")[-1] == {
        "level": "p3", "label": "Проявление", "value": "открытое пламя",
    }
    assert tree_path_for_code(graph, "нет-кода") == []
