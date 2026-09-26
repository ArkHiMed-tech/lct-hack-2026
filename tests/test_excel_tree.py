from openpyxl import Workbook

from data_transfer.tree_from_excel import (
    build_incident_graph,
    get_next_levels,
    load_incident_graph,
    save_incident_graph,
)


def test_build_incident_graph_supports_hierarchical_lookup(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            None,
            None,
            None,
            None,
            None,
            "Пожары и задымления",
            "на улице",
            "мусор",
            "открытое пламя",
            None,
        ]
    )
    ws.append(
        [
            None,
            None,
            None,
            None,
            None,
            "Пожары и задымления",
            "на улице",
            "трава",
            "дым",
            None,
        ]
    )
    ws.append(
        [
            None,
            None,
            None,
            None,
            None,
            "Пожары и задымления",
            "в помещении",
            "электрика",
            "короткое замыкание",
            None,
        ]
    )
    ws.append(
        [
            None,
            None,
            None,
            None,
            None,
            "Пожары и задымления",
            "в помещении",
            "газ",
            "запах газа",
            None,
        ]
    )

    path = tmp_path / "incident_tree.xlsx"
    wb.save(path)

    graph = build_incident_graph(path)

    assert get_next_levels(graph, []) == ["Пожары и задымления"]
    assert get_next_levels(graph, ["Пожары и задымления"]) == [
        "на улице",
        "в помещении",
    ]
    assert get_next_levels(graph, ["Пожары и задымления", "на улице"]) == [
        "мусор",
        "трава",
    ]
    assert get_next_levels(graph, ["Пожары и задымления", "на улице", "мусор"]) == [
        "открытое пламя"
    ]
    assert get_next_levels(graph, "Пожары и задымления > на улице") == [
        "мусор",
        "трава",
    ]


def test_save_and_load_incident_graph(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(
        [
            None,
            None,
            None,
            None,
            None,
            "Пожары и задымления",
            "на улице",
            "мусор",
            "дым",
            None,
        ]
    )
    ws.append(
        [
            None,
            None,
            None,
            None,
            None,
            "Пожары и задымления",
            "в помещении",
            "электрика",
            "короткое замыкание",
            None,
        ]
    )

    source = tmp_path / "tree.xlsx"
    target = tmp_path / "tree.json"
    wb.save(source)

    graph = build_incident_graph(source)
    save_incident_graph(graph, target)
    loaded_graph = load_incident_graph(target)

    assert loaded_graph["root_children"] == ["Пожары и задымления"]
    assert get_next_levels(loaded_graph, ["Пожары и задымления"]) == [
        "на улице",
        "в помещении",
    ]
