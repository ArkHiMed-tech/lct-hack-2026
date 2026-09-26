from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from data_transfer.tree_from_excel import (
    build_incident_graph,
    get_next_levels,
    load_incident_graph,
    save_incident_graph,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_MISC_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX_PATH = Path(
    os.getenv(
        "INCIDENT_CLASSIFIER_XLSX",
        str(
            _PROJECT_ROOT
            / "data_transfer"
            / "Классификатор_происшествий_v_046_24_корректировка_МВД_+_Департамент.xlsx"
        ),
    )
)
DEFAULT_JSON_PATH = Path(
    os.getenv(
        "INCIDENT_CLASSIFIER_JSON",
        str(_MISC_DIR / "incident_graph.json"),
    )
)


def _normalize_label(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).lower()


def _coerce_path(groups: list[str | None]) -> list[str]:
    cleaned = [group.strip() for group in groups if group not in (None, "")]
    return cleaned


def _normalize_path(groups: list[str]) -> list[str]:
    return [group.strip() for group in groups if group and group.strip()]


def _normalized_get_next_levels(graph: dict[str, Any], path: list[str]) -> list[str]:
    normalized_path = _normalize_path(path)
    if not normalized_path:
        return list(graph.get("root_children", []))

    return get_next_levels(graph, normalized_path)


def get_incident_next_levels(
    *,
    group1: str | None = None,
    group2: str | None = None,
    group3: str | None = None,
    group4: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Return valid next levels for a selected classification path.

    Works both with group1/group2/... arguments and with a single path like
    'Пожары и задымления>на улице'.
    """
    if path is not None:
        groups = _normalize_path([part for part in path.split(">")])
    else:
        groups = _coerce_path([group1, group2, group3, group4])

    json_path = DEFAULT_JSON_PATH
    if json_path.exists():
        graph = load_incident_graph(json_path)
    else:
        graph = build_incident_graph(DEFAULT_XLSX_PATH)
        save_incident_graph(graph, json_path)

    normalized_path = _normalize_path(groups)
    next_levels = _normalized_get_next_levels(graph, normalized_path)
    return {
        "path": normalized_path,
        "next_levels": next_levels,
    }


def build_incident_graph_file(
    xlsx_path: str | os.PathLike[str] | None = None,
    json_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    source = Path(xlsx_path) if xlsx_path is not None else DEFAULT_XLSX_PATH
    target = Path(json_path) if json_path is not None else DEFAULT_JSON_PATH
    graph = build_incident_graph(source)
    save_incident_graph(graph, target)
    return graph


if __name__ == "__main__":
    result = get_incident_next_levels(group1="Пожары и задымления")
    print(json.dumps(result, ensure_ascii=False, indent=2))
