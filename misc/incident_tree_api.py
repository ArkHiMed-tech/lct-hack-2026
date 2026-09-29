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


# ---------------------------------------------------------------------------
# Классификатор происшествий (секция "classifier" графа v2, источник — xlsx).
# Дерево: раздел Г -> Группа -> Признак1 -> Признак2 -> Признак3 -> лист
# (Номер, Итоговый тип, Главная служба + диспетчеризация служб).
# Тип происшествия карточки — Итоговый тип классификатора,
# а не номера служб 101/102/103/104.
# ---------------------------------------------------------------------------

NO_RESPONSE_MARKER = "нет реагирования"

# Алиасы нормализованных значений старой формы (v1) -> значения классификатора.
WHERE_ALIASES = {
    "улица": "на улице",
    "транспорт": "транспорт",
    "дом": "жилой дом",
    "здание / объект": "объект",
    "опасный объект": "объект",
}


def normalize_token(value: str | None) -> str:
    """Нормализация для сопоставления: нижний регистр, ё->е, без пунктуации."""
    text = str(value or "").lower().replace("ё", "е")
    for ch in "‐‑‒–—―.,;:!?()«»\"'":
        text = text.replace(ch, " ")
    return " ".join(text.split())


def _tokens_match(short: str, long: str) -> bool:
    a, b = normalize_token(short), normalize_token(long)
    return bool(a) and bool(b) and (a == b or a in b or b in a)


def content_tokens(value: str | None) -> set[str]:
    """Значимые токены (длина >= 3) для сопоставления ТЭГов с путём листа."""
    return {t for t in normalize_token(value).split() if len(t) >= 3}


def _overlap_count(a: set[str], b: set[str]) -> int:
    """Пересечение токенов: точное + нечёткое (опечатки вида газо/газа)."""
    import difflib

    rest = set(b)
    count = 0
    for token in a:
        if token in rest:
            count += 1
            rest.discard(token)
            continue
        for other in list(rest):
            if abs(len(token) - len(other)) <= 2 and difflib.SequenceMatcher(
                None, token, other
            ).ratio() >= 0.85:
                count += 1
                rest.discard(other)
                break
    return count


SMELL_TOKENS = {"запах", "гари"}


def get_classifier(graph: dict[str, Any] | None = None) -> dict[str, Any]:
    g = graph or load_incident_graph()
    return g.get("classifier", {}) if isinstance(g, dict) else {}


def classifier_leaves(
    graph: dict[str, Any] | None = None,
    g: int | None = None,
    groups: list[str] | None = None,
    visible_only: bool = False,
) -> list[dict[str, Any]]:
    leaves = list(get_classifier(graph).get("leaves", []))
    if g is not None:
        leaves = [leaf for leaf in leaves if leaf.get("g") == g]
    if groups:
        wanted = {normalize_token(x) for x in groups}
        leaves = [leaf for leaf in leaves if normalize_token(leaf.get("group")) in wanted]
    if visible_only:
        leaves = [leaf for leaf in leaves if leaf.get("operator_visible")]
    return leaves


def leaves_for_root(
    graph: dict[str, Any] | None = None, title: str | None = None
) -> list[dict[str, Any]]:
    """Листья классификатора, покрывающие корень операторского выбора (root_map)."""
    classifier = get_classifier(graph)
    rule = (classifier.get("root_map", {}) or {}).get(title or "", {})
    if not rule:
        return []
    leaves = classifier_leaves(graph)
    if rule.get("g"):
        leaves = [leaf for leaf in leaves if leaf.get("g") in rule["g"]]
    if rule.get("groups"):
        wanted = {normalize_token(x) for x in rule["groups"]}
        leaves = [leaf for leaf in leaves if normalize_token(leaf.get("group")) in wanted]
    if rule.get("services_any"):
        wanted = set(rule["services_any"])
        leaves = [
            leaf for leaf in leaves
            if wanted & set((leaf.get("dispatch") or {}).keys())
        ]
    return leaves


def match_leaf(
    graph: dict[str, Any] | None = None,
    where: str | None = None,
    detail: str | None = None,
    sign: str | None = None,
    type_title: str | None = None,
) -> dict[str, Any] | None:
    """Лучший лист классификатора под ТЭГи карточки (старая форма v1).

    Сопоставление — по токенному перекрытию ТЭГов (где/детализация/признак)
    с полным путём листа: вес детализации ×2. Пламя: нужно пересечение
    по детализации и счёт >= 3. Запах гари: счёт по где + удвоенному
    признаку, нужно >= 4 при совпадении признака. Иначе None (эвристики).
    """
    g = graph or load_incident_graph()
    pool = leaves_for_root(g, type_title) if type_title else classifier_leaves(g)
    if not pool:
        return None

    norm_where = normalize_token(where)
    where_src = WHERE_ALIASES.get(norm_where, norm_where)
    wt = content_tokens(where_src) if where_src else set()
    dt = content_tokens(detail)
    st = content_tokens(sign)
    is_smell = SMELL_TOKENS <= st

    best: dict[str, Any] | None = None
    best_score = 0
    for leaf in pool:
        lt = content_tokens(" ".join(leaf.get("path", []) or []))
        if not lt:
            continue
        if is_smell and not dt:
            s_sign = _overlap_count(st, lt)
            if s_sign < 2:
                continue
            score = _overlap_count(wt, lt) + 2 * s_sign
        else:
            if not dt or not _overlap_count(dt, lt):
                continue
            score = (
                _overlap_count(wt, lt)
                + 2 * _overlap_count(dt, lt)
                + _overlap_count(st, lt)
            )
        if score > best_score:
            best, best_score = leaf, score
    if best is None or best_score < (4 if (is_smell and not dt) else 3):
        return None
    return best


def dispatch_for_leaf(
    graph: dict[str, Any] | None,
    leaf: dict[str, Any],
    flags: dict[str, bool] | None = None,
) -> dict[str, str]:
    """Диспетчеризация листа: выбор вариантов колонок по флагам карточки.

    flags: nd/ul/pp/violation/victims/victims_absent/gas/threat/medical/evac/
    crowd/block/tunnel/pesh/av/sites/stroyka/pozhar/moscow. Вариант с флагом
    приоритетнее базы; значение-маркер «нет реагирования» означает
    отсутствие выезда. Возвращает {service_group_id: значение}.
    """
    g = graph or load_incident_graph()
    flags = flags or {}
    services = {s["id"]: s for s in get_classifier(g).get("services", [])}
    dispatch = leaf.get("dispatch", {}) or {}
    out: dict[str, str] = {}
    for gid, meta in services.items():
        base_sid = gid  # вариант без флага носит id группы
        chosen: str | None = None
        for col in meta.get("columns", []):
            flag = col.get("flag")
            if flag and flags.get(flag) and col["variant"] in dispatch:
                chosen = dispatch[col["variant"]]
                break
        if chosen is None and base_sid in dispatch:
            chosen = dispatch[base_sid]
        if chosen and normalize_token(chosen) != NO_RESPONSE_MARKER:
            out[gid] = chosen
    return out


def service_display_name(
    graph: dict[str, Any] | None, group_id: str
) -> str:
    """Каноническое имя службы для карточки (каталог serviceCatalog.js)."""
    g = graph or load_incident_graph()
    for meta in get_classifier(g).get("services", []):
        if meta.get("id") == group_id:
            return meta.get("catalog") or meta.get("title", group_id)
    return group_id


def compact_leaf(leaf: dict[str, Any], sections: dict[int, str] | None = None) -> dict[str, Any]:
    """Компактная карточка листа для индекса фронта."""
    sec_title = ""
    if sections is not None:
        sec_title = sections.get(leaf.get("g"), "")
    return {
        "code": leaf.get("code"),
        "result": leaf.get("result"),
        "path": leaf.get("path", []),
        "group": leaf.get("group"),
        "section": {"g": leaf.get("g"), "title": sec_title},
        "main": leaf.get("main"),
        "operator_visible": leaf.get("operator_visible", True),
    }


def search_leaves(
    graph: dict[str, Any] | None = None,
    query: str | None = None,
    limit: int = 50,
    visible_only: bool = True,
) -> list[dict[str, Any]]:
    """Поиск листьев по подстроке (результат + путь + группа)."""
    g = graph or load_incident_graph()
    classifier = get_classifier(g)
    sections = {s["g"]: s["title"] for s in classifier.get("sections", [])}
    tokens = [t for t in normalize_token(query).split() if len(t) >= 2] if query else []
    out = []
    for leaf in classifier.get("leaves", []) or []:
        if visible_only and not leaf.get("operator_visible", True):
            continue
        if tokens:
            hay = normalize_token(
                " ".join(
                    [str(leaf.get("result") or "")]
                    + list(leaf.get("path", []) or [])
                    + [str(leaf.get("group") or "")]
                )
            )
            if not all(tok in hay for tok in tokens):
                continue
        out.append(compact_leaf(leaf, sections))
        if len(out) >= limit:
            break
    return out


def get_leaf_by_code(
    graph: dict[str, Any] | None = None, code: str | None = None
) -> dict[str, Any] | None:
    g = graph or load_incident_graph()
    for leaf in get_classifier(g).get("leaves", []) or []:
        if str(leaf.get("code")) == str(code):
            return leaf
    return None


if __name__ == "__main__":
    g = load_incident_graph()
    print("types:", len(g.get("root_children", [])))
    print(json.dumps(get_incident_next_levels(path="101"), ensure_ascii=False, indent=1)[:800])
    print(json.dumps(
        get_incident_next_levels(path="101>Улица>Открытое пламя / Дым>Есть доступ>Мусор"),
        ensure_ascii=False, indent=1,
    ))
