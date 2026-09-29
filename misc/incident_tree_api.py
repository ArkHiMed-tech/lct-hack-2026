"""Классификатор «Что случилось?» — переписан под ТЗ КАРТОЧКА 112.docx.

Источник: Таблица 0 (51 значение: 101/102/103/104 + 47 типов) +
подписи скриншотов ветки 101-Пожар
(УЛИЦА / ОТКРЫТОЕ ПЛАМЯ-дыМ / ДОСТУП / МУСОР / ТОННЕЛЬ-ПЕРЕХОД / УГРОЗА / НАРУШЕНИЕ).

Формат incident_graph.json:
  root_children: 51 строка уровня 1
  type_meta[title] = {"groups": [...], "kind": "fire101"|"generic"}
  tag_sets: именованные наборы ТЭГов
  children: материализованные пути глубины <= 4
  flow: порядок шагов мастера для fire101 / generic
"""
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

# Хвост ветки 101 после выбора детализации (не материализован в JSON,
# возвращается ручкой по глубине пути — одинаков для всех веток пожара).
_FIRE_TAIL: list[list[str]] = [
    ["Тоннель", "Пешеходный переход"],  # place
    ["Да", "Нет"],  # threat
    ["Есть правонарушение"],  # violation (single) + фронт добавит "Нет" как сброс
    ["Да", "Нет"],  # medical
    ["Да", "Нет"],  # evac
    ["Да", "Нет", "Нет данных"],  # gas
]

_FIRE_TAIL_KEYS = ["place", "threat", "violation", "medical", "evac", "gas"]


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
    return ">".join(p.strip().lower() for p in path if p and p.strip())


def load_incident_graph(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    p = Path(path) if path else Path(os.getenv("INCIDENT_CLASSIFIER_JSON", str(DEFAULT_JSON_PATH)))
    with p.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def get_incident_types(graph: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Полный список уровня 1: 51 тип с группами служб и видом ветки."""
    g = graph or load_incident_graph()
    meta = g.get("type_meta", {})
    out: list[dict[str, Any]] = []
    for title in g.get("root_children", []):
        m = meta.get(title, {})
        out.append({"title": title, "groups": list(m.get("groups", [])), "kind": m.get("kind", "generic")})
    return out


def get_type_meta(graph: dict[str, Any], title: str) -> dict[str, Any] | None:
    meta = graph.get("type_meta", {})
    if title in meta:
        return {"title": title, **meta[title]}
    low = title.strip().lower()
    for k, v in meta.items():
        if k.strip().lower() == low:
            return {"title": k, **v}
    return None


def _fire_tail_for_depth(depth_after_type: int) -> list[str]:
    """depth_after_type: сколько шагов выбрано после типа (where=1, sign=2, ...)."""
    # materialized: 1->signs, 2->access, 3->access? нет: type>w>s>a => details (depth 4 = detail выбран)
    # depth 4 (detail) -> place, 5 -> threat, 6 -> violation, 7 -> medical, 8 -> evac, 9 -> gas, 10+ -> []
    idx = depth_after_type - 4
    if 0 <= idx < len(_FIRE_TAIL):
        return list(_FIRE_TAIL[idx])
    return []


def get_next_levels(
    graph: dict[str, Any], path: str | list[str] | tuple[str, ...] | None
) -> list[str]:
    if path is None:
        return list(graph.get("root_children", []))
    current = _clean_path_parts(path.split(">")) if isinstance(path, str) else _clean_path_parts(path)
    if not current:
        return list(graph.get("root_children", []))

    children = graph.get("children", {})
    direct = _lookup_path_key(current)
    if direct in children:
        return list(children[direct])

    norm = _canonical_key(current)
    for key, value in children.items():
        if isinstance(key, str) and _canonical_key(key.split(">")) == norm:
            return list(value)

    # Нематериализованный хвост ветки fire101 (place/threat/...): вычисляем по глубине.
    meta = get_type_meta(graph, current[0])
    if meta and meta.get("kind") == "fire101" and len(current) >= 5:
        tail = _fire_tail_for_depth(len(current) - 1)
        if tail:
            return tail
    return []


def get_incident_next_levels(
    *,
    group1: str | None = None,
    group2: str | None = None,
    group3: str | None = None,
    group4: str | None = None,
    group5: str | None = None,
    group6: str | None = None,
    group7: str | None = None,
    group8: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    """Контракт ручки: path + next_levels + is_leaf + meta уровня 1."""
    if path is not None:
        groups = _clean_path_parts(path.split(">"))
    else:
        groups = _clean_path_parts([group1, group2, group3, group4, group5, group6, group7, group8])

    graph = load_incident_graph()
    nxt = get_next_levels(graph, groups)
    meta = get_type_meta(graph, groups[0]) if groups else None
    return {
        "path": groups,
        "next_levels": nxt,
        "is_leaf": len(nxt) == 0,
        "meta": meta,
        "tag_sets": graph.get("tag_sets", {}),
        "flow": graph.get("flow", {}),
    }


if __name__ == "__main__":
    g = load_incident_graph()
    print("types:", len(g.get("root_children", [])))
    print(json.dumps(get_incident_next_levels(path="101"), ensure_ascii=False, indent=1)[:800])
    print(json.dumps(
        get_incident_next_levels(path="101>Улица>Открытое пламя / Дым>Есть доступ>Мусор"),
        ensure_ascii=False, indent=1,
    ))
