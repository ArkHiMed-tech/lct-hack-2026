from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

_MISC_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_PATH = Path(
    os.getenv(
        "INCIDENT_CLASSIFIER_JSON",
        str(_MISC_DIR / "incident_graph.json"),
    )
)


def _clean_path_parts(parts: Iterable[str | None]) -> list[str]:
    cleaned: list[str] = []
    for part in parts:
        if part is None:
            continue
        value = str(part).strip()
        if value:
            cleaned.append(value)
    return cleaned


def _lookup_path_key(path: list[str]) -> str:
    return ">".join(path)


def _canonical_key(path: list[str]) -> str:
    return ">".join(part.strip() for part in path if part and part.strip()).lower()


def load_incident_graph(path: str | os.PathLike[str]) -> dict[str, Any]:
    """Load the already prepared incident tree JSON."""
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data


def get_next_levels(
    graph: dict[str, Any], path: str | list[str] | tuple[str, ...] | None
) -> list[str]:
    """Return all next-level children for the selected path from the JSON graph."""
    if path is None:
        return list(graph.get("root_children", []))

    if isinstance(path, str):
        current = _clean_path_parts(path.split(">"))
    else:
        current = _clean_path_parts(path)

    if not current:
        return list(graph.get("root_children", []))

    children = graph.get("children", {})
    direct_key = _lookup_path_key(current)

    if direct_key in children:
        return list(children[direct_key])

    normalized_key = _canonical_key(current)
    for key, value in children.items():
        if isinstance(key, str) and _canonical_key(key.split(">")) == normalized_key:
            return list(value)

    for key, value in children.items():
        if isinstance(key, tuple) and _canonical_key(list(key)) == normalized_key:
            return list(value)

    return []


def get_incident_next_levels(
    *,
    group1: str | None = None,
    group2: str | None = None,
    group3: str | None = None,
    group4: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Return the same response contract as before: path plus next_levels."""
    if path is not None:
        groups = _clean_path_parts(path.split(">"))
    else:
        groups = _clean_path_parts([group1, group2, group3, group4])

    json_path = Path(os.getenv("INCIDENT_CLASSIFIER_JSON", str(DEFAULT_JSON_PATH)))
    if not json_path.exists():
        raise FileNotFoundError(
            f"Incident tree JSON not found: {json_path}. "
            "Place the generated incident_graph.json file in the project and try again."
        )

    graph = load_incident_graph(json_path)
    return {
        "path": groups,
        "next_levels": get_next_levels(graph, groups),
    }


if __name__ == "__main__":
    result = get_incident_next_levels(group1="Пожары и задымления")
    print(json.dumps(result, ensure_ascii=False, indent=2))
