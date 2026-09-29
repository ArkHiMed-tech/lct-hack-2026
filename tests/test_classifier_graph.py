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
    assert len(sections) == 23  # сепараторы 1-23; Г=24 без сепаратора
    assert len(leaves) == 1283  # 7- и 8-значные Номера, разделы 1-24
    codes = [leaf["code"] for leaf in leaves]
    assert len(set(codes)) == len(codes)
    assert all(leaf["path"] for leaf in leaves)
    filled = {leaf["g"] for leaf in leaves}
    assert filled == set(range(1, 25))


def test_graph_v3_shape_no_legacy_keys():
    current = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    assert current["version"] == 5
    for key in ("root", "root_children", "type_meta", "tag_sets", "children", "flow"):
        assert key not in current, f"legacy key remains: {key}"
    classifier = current["classifier"]
    assert classifier["leaf_count"] == 1283
    assert len(classifier["tree"]) == 24  # все разделы заполнены


def test_classifier_section_shape():
    graph = load_incident_graph()
    classifier = graph["classifier"]
    assert classifier["leaf_count"] == 1283
    assert len(classifier["sections"]) == 24  # 23 сепаратора + БПЛА
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


def test_new_sections_reachable_and_valid():
    from misc.card_generator import generate_card as gen

    graph = load_incident_graph()
    by_code = {leaf["code"]: leaf for leaf in classifier_leaves(graph)}
    for code in ("24010000", "13010100", "17010100", "22010000", "15010100"):
        leaf = by_code[code]
        assert leaf["path"], code
    seen_sections = set()
    seen_mains = set()
    for seed in range(400):
        payload = gen(seed=seed)["payload"]
        assert validate_card_payload(payload) == ""
        sec = payload.get("classifier_section")
        if sec:
            seen_sections.add(sec["g"])
            seen_mains.add(payload.get("main_service"))
    assert len(seen_sections) >= 20, sorted(seen_sections)
    assert 24 in seen_sections
    assert {"AMBULANCE", "MOSGAZ"} <= seen_mains


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
    assert [r["g"] for r in tree] == list(range(1, 25))
    reached = _walk_all_leaves(tree)
    codes = [c for c, _ in reached]
    visible = {leaf["code"] for leaf in classifier_leaves(graph, visible_only=True)}
    assert set(codes) == visible
    # Каждый лист ровно один раз; единственный дубль пути (БПЛА/БВС Регион)
    # хранит оба кода в одном узле.
    assert len(codes) == len(visible)
    dup = get_tree_children(
        graph, g=24,
        p1="летит, готовят к запуску,упал/ столкнулся, нет взрыва возгорания",
        p2="Регион",
    )
    assert {s["code"] for s in dup["selectable"]} == {"24120100", "24120200"}
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
    assert [b["g"] for b in step0["buttons"]] == list(range(1, 25))
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


def test_auto_flag_matrix():
    from misc.incident_tree_api import get_classifier

    graph = load_incident_graph()
    by_id = {s["id"]: s for s in get_classifier(graph)["services"]}
    responders = {
        "mchs101", "odps", "mgpss", "mvd", "smp", "mosgaz", "cemp",
        "codd", "mosbez", "mkp", "dgp", "gupmsr", "vodokanal", "moblgaz",
    }
    assert {gid for gid, m in by_id.items() if m.get("auto")} == responders
    for gid in ("apperat", "ntu", "terr_oiv", "terr_oiv_tinao", "fso",
                "depkult", "gorhoz", "cukb", "oati", "rosgvard"):
        assert by_id[gid].get("auto") is False, gid


def test_strict_no_fallback_on_empty_variant():
    from misc.incident_tree_api import dispatch_for_leaf, get_leaf_by_code

    graph = load_incident_graph()
    leaf = get_leaf_by_code(graph, "1010101")
    assert "mchs101_nd" not in (leaf.get("dispatch") or {})
    assert "mchs101" in (leaf.get("dispatch") or {})
    out = dispatch_for_leaf(graph, leaf, {"nd": True})
    assert "mchs101" not in out  # пустое окошко НД = нет выезда, без fallback


def test_informed_split():
    from misc.incident_tree_api import (
        dispatch_for_leaf, get_leaf_by_code, informed_for_leaf,
        service_display_name,
    )

    graph = load_incident_graph()
    leaf = get_leaf_by_code(graph, "1010101")
    resp = dispatch_for_leaf(graph, leaf, {})
    info = informed_for_leaf(graph, leaf, {})
    assert set(resp) & set(info) == set()
    assert "mchs101" in resp and "apperat" not in resp
    assert "apperat" in info and "mchs101" not in info
    names = [service_display_name(graph, gid) for gid in info]
    assert "Аппарат МЭРА" in names


def test_cascade_bpla_section():
    graph = load_incident_graph()
    step0 = get_tree_children(graph)
    assert len(step0["buttons"]) == 24
    bpla = next(b for b in step0["buttons"] if b["g"] == 24)
    assert bpla["value"] == "БПЛА"
    step1 = get_tree_children(graph, g=24)
    assert "готовят к запуску, летит" in [b["value"] for b in step1["buttons"]]
    leaf = get_tree_children(graph, g=24, p1="готовят к запуску, летит")
    assert leaf["buttons"] == []
    assert leaf["selectable"] == [{"code": "24010000", "result": "БПЛА"}]
    crumbs = tree_path_for_code(graph, "24010000")
    assert [c["value"] for c in crumbs] == ["БПЛА", "готовят к запуску, летит"]


def test_cascade_duplicate_path_offers_both():
    graph = load_incident_graph()
    step = get_tree_children(
        graph, g=24,
        p1="летит, готовят к запуску,упал/ столкнулся, нет взрыва возгорания",
        p2="Регион",
    )
    assert step["buttons"] == []
    assert {s["code"] for s in step["selectable"]} == {"24120100", "24120200"}


def test_cascade_new_sections():
    graph = load_incident_graph()
    gas = get_tree_children(graph, g=13, p1="Запах газа на улице", p2="Коллектор")
    assert gas["selectable"] == [
        {"code": "13010100", "result": "Запах бытового газа в коллекторе"}
    ]
    man = get_tree_children(graph, g=17, p1="Человек в опасности", p2="Человек лежит")
    assert man["selectable"] == [{"code": "17010100", "result": "Лежит человек"}]
