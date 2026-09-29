"""Навигация по дереву классификатора происшествий (xlsx, граф v3).

Дерево: раздел (9 шт) -> Место (Признак1) -> Что (Признак2) ->
Проявление (Признак3) -> лист (Номер + Итоговый тип + диспетчеризация).
Дети каждого узла вычислены пересечением строк классификатора
(см. misc/build_incident_graph.py), только видимые оператору ветви.

Тип происшествия карточки — Итоговый тип классификатора,
а не номера служб 101/102/103/104.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_MISC_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_PATH = Path(
    os.getenv(
        "INCIDENT_CLASSIFIER_JSON",
        str(_MISC_DIR / "incident_graph.json"),
    )
)

# Уровни каскада: раздел -> место -> что -> проявление.
TREE_LEVELS = ["section", "p1", "p2", "p3"]
LEVEL_LABELS = {
    "section": "Раздел",
    "p1": "Место",
    "p2": "Что",
    "p3": "Проявление",
}


def load_incident_graph(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    p = Path(path) if path else Path(os.getenv("INCIDENT_CLASSIFIER_JSON", str(DEFAULT_JSON_PATH)))
    with p.open("r", encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# Навигация по дереву: раздел -> Место -> Что -> Проявление -> лист.
# Путь задаётся значениями [g, p1?, p2?, p3?]; на каждом шаге возвращаются
# ВСЕ доступные варианты разом + листья, заканчивающиеся в текущем узле
# (узел может быть одновременно выбираемым типом и родителем).
# ---------------------------------------------------------------------------

def _tree_roots(graph: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    g = graph or load_incident_graph()
    return list(get_classifier(g).get("tree", []) or [])


def _find_section_node(
    graph: dict[str, Any] | None, g: int
) -> dict[str, Any] | None:
    for root in _tree_roots(graph):
        if root.get("g") == g:
            return root
    return None


def _find_child(node: dict[str, Any], value: str) -> dict[str, Any] | None:
    for child in node.get("children", []) or []:
        if child.get("value") == value:
            return child
    return None


def get_tree_children(
    graph: dict[str, Any] | None = None,
    g: int | None = None,
    p1: str | None = None,
    p2: str | None = None,
    p3: str | None = None,
) -> dict[str, Any]:
    """Один шаг каскада. Пустой путь -> 9 разделов.

    Возвращает:
      breadcrumb: [{level, label, value}] пройденный путь;
      buttons: [{value, has_children, leaf_count}] все варианты разом;
      selectable: [{code, result}] листья ровно в текущем узле (кнопки «Выбрать»).
    """
    graph = graph or load_incident_graph()
    by_code = {leaf["code"]: leaf for leaf in get_classifier(graph).get("leaves", []) or []}
    breadcrumb: list[dict[str, Any]] = []
    if g is None:
        buttons = [
            {
                "value": root.get("title"),
                "g": root.get("g"),
                "has_children": bool(root.get("children")),
                "leaf_count": 0,
            }
            for root in _tree_roots(graph)
        ]
        return {"breadcrumb": breadcrumb, "buttons": buttons, "selectable": []}

    root = _find_section_node(graph, g)
    if root is None:
        return {"breadcrumb": breadcrumb, "buttons": [], "selectable": []}
    breadcrumb.append(
        {"level": "section", "label": LEVEL_LABELS["section"],
         "value": root.get("title"), "g": root.get("g")}
    )
    node: dict[str, Any] | None = root
    for depth, part in (("p1", p1), ("p2", p2), ("p3", p3)):
        if part is None or node is None:
            break
        node = _find_child(node, part)
        if node is None:
            return {"breadcrumb": breadcrumb, "buttons": [], "selectable": []}
        breadcrumb.append(
            {"level": depth, "label": LEVEL_LABELS[depth], "value": part}
        )
    if node is None:
        return {"breadcrumb": breadcrumb, "buttons": [], "selectable": []}

    buttons = []
    for child in node.get("children", []) or []:
        sub = len(child.get("leaves", []) or []) + sum(
            len(c.get("leaves", []) or []) for c in child.get("children", []) or []
        )
        buttons.append(
            {"value": child.get("value"),
             "has_children": bool(child.get("children")),
             "leaf_count": sub}
        )
    selectable = []
    for code in node.get("leaves", []) or []:
        leaf = by_code.get(code)
        if leaf is not None:
            selectable.append({"code": code, "result": leaf.get("result")})
    return {"breadcrumb": breadcrumb, "buttons": buttons, "selectable": selectable}


def tree_path_for_code(
    graph: dict[str, Any] | None = None, code: str | None = None
) -> list[dict[str, Any]]:
    """Breadcrumb для листа по Номеру: [раздел, место?, что?, проявление?]."""
    leaf = get_leaf_by_code(graph, code)
    if leaf is None:
        return []
    g = graph or load_incident_graph()
    sections = {s["g"]: s["title"] for s in get_classifier(g).get("sections", [])}
    crumbs = [
        {"level": "section", "label": LEVEL_LABELS["section"],
         "value": sections.get(leaf.get("g"), ""), "g": leaf.get("g")}
    ]
    for depth, part in zip(("p1", "p2", "p3"), leaf.get("path", []) or []):
        crumbs.append({"level": depth, "label": LEVEL_LABELS[depth], "value": part})
    return crumbs


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


def _dispatch_core(
    graph: dict[str, Any] | None,
    leaf: dict[str, Any],
    flags: dict[str, bool] | None,
    auto: bool | None,
) -> dict[str, str]:
    """Ядро диспетчеризации. auto=True/False — только выезжающие/уведомляемые,
    None — все группы. Строгий режим: стоят свои флаги -> ответ только
    из вариантных ячеек (пустой вариант = нет выезда, без fallback на базу);
    своих флагов нет -> база."""
    g = graph or load_incident_graph()
    flags = flags or {}
    services = {s["id"]: s for s in get_classifier(g).get("services", [])}
    dispatch = leaf.get("dispatch", {}) or {}
    out: dict[str, str] = {}
    for gid, meta in services.items():
        if auto is not None and bool(meta.get("auto", True)) is not auto:
            continue
        base_sid = gid  # вариант без флага носит id группы
        own_flags = [
            col for col in meta.get("columns", [])
            if col.get("flag") and flags.get(col["flag"])
        ]
        chosen: str | None = None
        if own_flags:
            for col in own_flags:
                if col["variant"] in dispatch:
                    chosen = dispatch[col["variant"]]
                    break
            if chosen is None:
                continue  # строгий режим: пустое окошко варианта = нет выезда
        elif base_sid in dispatch:
            chosen = dispatch[base_sid]
        if chosen and normalize_token(chosen) != NO_RESPONSE_MARKER:
            out[gid] = chosen
    return out


def dispatch_for_leaf(
    graph: dict[str, Any] | None,
    leaf: dict[str, Any],
    flags: dict[str, bool] | None = None,
) -> dict[str, str]:
    """Диспетчеризация листа: ВЫЕЗЖАЮЩИЕ службы (auto-группы).

    flags: nd/ul/pp/violation/victims/victims_absent/gas/threat/medical/evac/
    crowd/block/tunnel/pesh/av/sites/stroyka/pozhar/moscow. Свои флаги стоят ->
    ответ только из вариантных ячеек; значение-маркер «нет реагирования»
    означает отсутствие выезда. Возвращает {service_group_id: значение}.
    """
    return _dispatch_core(graph, leaf, flags, auto=True)


def informed_for_leaf(
    graph: dict[str, Any] | None,
    leaf: dict[str, Any],
    flags: dict[str, bool] | None = None,
) -> dict[str, str]:
    """УВЕДОМЛЯЕМЫЕ службы листа (маркерные группы, синие плашки).
    Та же строгая логика вариантов, что в dispatch_for_leaf."""
    return _dispatch_core(graph, leaf, flags, auto=False)


# Главная служба классификатора (кол. 12 xlsx) -> группа ВИС
# (колонки «Классификатор ...» / сервисная группа графа).
# Непокрытые/составные main без маппинга -> fallback на Итоговый тип.
MAIN_TO_VIS_GID: dict[str, str] = {
    "MCHS": "mchs101",
    "Police": "mvd",
    "AMBULANCE": "smp",
    "MOSGAZ": "mosgaz",
    "MOSLIFT": "moslift",
    "AUTOROADS": "avtodor",
    "MOSVODOCANAL": "vodokanal",
    "METRO": "metro",
    "OEK": "oek",
    "MOSGORTRANS": "mostrans",
    "MOESK": "moesk",
    "MOEK": "moek",
    "MZD": "rzd",
    "MGTS": "mgts",
    "MOSVODOSTOK": "vodostok",
    "MOSCOLLECTOR": "moskollektor",
    "GORMOST": "gormost",
    "GKH": "gorhoz",
    "ZODD": "codd",
    "MSPPN": "msppn",
    "DepEco": "dppios",
    "ZEMP": "cemp",
    "Dep.tszn": "tszn",
    "МСР": "gupmsr",
}

# Маркер информирования «карточка-112» (+ известные опечатки): для ВИС-класса
# считается пустым значением -> fallback на Итоговый тип.
_VIS_MARKER_RE = r"^картт?очк[аи][\s\-]*\d*$"
_VIS_MARKER_TYPOS = {"картчока-112"}


def _vis_value_empty(value: str | None) -> bool:
    import re

    if value is None:
        return True
    text = str(value).strip()
    if not text:
        return True
    norm = normalize_token(text)
    if norm == NO_RESPONSE_MARKER:
        return True
    squashed = text.lower().replace("ё", "е").replace(" ", "")
    return bool(re.match(_VIS_MARKER_RE, squashed)) or squashed in _VIS_MARKER_TYPOS


def resolve_vis_gid(main: str | None) -> str | None:
    """Группа ВИС по Главной службе; составные ('METRO, MZD') — по первому
    известному токену. None — нет маппинга (fallback на Итоговый тип)."""
    for token in str(main or "").replace(",", " ").split():
        if token in MAIN_TO_VIS_GID:
            return MAIN_TO_VIS_GID[token]
    return None


def vis_class_for_leaf(
    graph: dict[str, Any] | None,
    leaf: dict[str, Any],
    flags: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """ВИС класс листа: одно значение по Главной службе.

    Строгая семантика вариантов как в _dispatch_core: стоят свои флаги
    группы -> только вариантные ячейки (пустое окошко = нет значения);
    своих флагов нет -> базовая ячейка. Пустое/маркер («нет реагирования»,
    «карточка-112») -> fallback на Итоговый тип (leaf.result).

    Возвращает {gid, value, is_fallback}.
    """
    g = graph or load_incident_graph()
    flags = flags or {}
    result = (leaf.get("result") or "").strip()
    gid = resolve_vis_gid(leaf.get("main"))
    if gid is None:
        return {"gid": None, "value": result, "is_fallback": True}
    columns = []
    for meta in get_classifier(g).get("services", []):
        if meta.get("id") == gid:
            columns = meta.get("columns", []) or []
            break
    dispatch = leaf.get("dispatch", {}) or {}
    own_flags = [c for c in columns if c.get("flag") and flags.get(c["flag"])]
    chosen: str | None = None
    if own_flags:
        for col in own_flags:
            val = dispatch.get(col["variant"])
            if val and not _vis_value_empty(val):
                chosen = val
                break
    else:
        base_variant = next(
            (c["variant"] for c in columns if not c.get("flag")), gid
        )
        val = dispatch.get(base_variant)
        if val and not _vis_value_empty(val):
            chosen = val
    if chosen:
        return {"gid": gid, "value": chosen, "is_fallback": False}
    return {"gid": gid, "value": result, "is_fallback": True}


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
    step0 = get_tree_children(g)
    print("sections:", [(b["g"], b["value"]) for b in step0["buttons"]])
    step1 = get_tree_children(g, g=1)
    print("g=1 buttons:", [b["value"] for b in step1["buttons"]])
    step3 = get_tree_children(g, g=1, p1="на улице", p2="мусор")
    print("fire/musor:", json.dumps(step3, ensure_ascii=False)[:300])
