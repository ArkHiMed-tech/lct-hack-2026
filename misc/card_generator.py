"""Генератор карточек 112 обходом дерева классификатора происшествий.

Обход: seed -> лист классификатора (Номер + путь Признак1→Признак2→Признак3,
только видимые оператору) -> address -> caller -> victims(+флаги) ->
services (диспетчеризация листа) -> narrative.

Тип происшествия карточки — Итоговый тип классификатора (например
«пожар: мусор»), а не номера служб 101/102/103/104. Инфо-типы без выезда
(«Отмена вызова», справки и т.д.) в классификаторе отсутствуют и идут
отдельной веткой без диспетчеризации.

Возвращает payload формата POST /api/reports/create.
Чистый модуль: без FastAPI/SQL, детерминирован seed'ом (random.Random).
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path
from typing import Any

from misc.incident_tree_api import (
    classifier_leaves,
    dispatch_for_leaf,
    get_leaf_by_code,
    informed_for_leaf,
    load_incident_graph,
    service_display_name,
)

_MISC_DIR = Path(__file__).resolve().parent
DEFAULT_CARD_GRAPH_PATH = Path(
    os.getenv("CARD_GRAPH_JSON", str(_MISC_DIR / "card_graph.json"))
)

INFO_TYPES = [
    "Отмена вызова",
    "Ошибочно набран номер",
    "Тестовый вызов",
    "Тренировка",
    "Передача дежурства",
    "Нецелевой вызов",
    "Консультация",
    "Вызов на иностранном языке",
    "Справка 101",
    "Справка 102",
    "Справка 103",
    "Справка 104",
    "Справка ГИБДД",
    "Справка Городское хозяйство",
    "Справка МЧС",
    "Благодарность службам",
    "Жалоба на действие или бездействие служб",
    "Технический сбой (сбой в работе с оборудованием 112 Москва)",
]

EMPTY_TAGS = {
    "attr1": "",
    "attr2": "",
    "attr3": "",
    "no_access": False,
    "threat": False,
    "violation": False,
    "medical": False,
    "evac": False,
    "gas": False,
    "tagDesc": "",
}

FLAG_LABELS = {
    "no_access": "нет доступа",
    "threat": "угроза людям",
    "violation": "правонарушение",
    "medical": "мед. помощь",
    "evac": "треб. эвакуация",
    "gas": "газификация",
}


def load_card_graph(path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    p = Path(path) if path else Path(
        os.getenv("CARD_GRAPH_JSON", str(DEFAULT_CARD_GRAPH_PATH))
    )
    with p.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _pick(rng: random.Random, options: list[str]) -> str:
    if not options:
        return ""
    return rng.choice(options)


def validate_card_payload(payload: dict[str, Any]) -> str:
    """Проверка карточки. Пусто = валидно."""
    if not str(payload.get("what", "")).strip():
        return "Выберите «Что случилось?» — поле обязательно."
    if payload.get("classifier_code"):
        tags = payload.get("tags", {})
        if not tags.get("attr1"):
            return "Укажите Признак 1 классификатора."
    if not str(payload.get("caller_name", "")).strip():
        return "Заполните «ФИО заявителя»."
    if not payload.get("caller_status"):
        return "Выберите «Статус заявителя»."
    return ""


def _phone(rng: random.Random, prefix: str) -> str:
    return f"+7 ({prefix}) {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}"


def _resolve_override_leaf(
    graph: dict[str, Any], override: str
) -> dict[str, Any] | None:
    """Override типа: точный Номер, точный Итоговый тип или подстрока результата."""
    leaves = classifier_leaves(graph, visible_only=True)
    by_code = get_leaf_by_code(graph, override)
    if by_code is not None:
        return by_code
    low = override.strip().lower()
    for leaf in leaves:
        if str(leaf.get("result") or "").strip().lower() == low:
            return leaf
    for leaf in leaves:
        if low in str(leaf.get("result") or "").lower():
            return leaf
    return None


def _walk_tree_leaf(
    rng: random.Random, graph: dict[str, Any], card: dict[str, Any]
) -> dict[str, Any]:
    """Спуск по дереву каскада (та же логика, что кнопки фронта):
    раздел (взвешенно) -> Место -> Что -> Проявление -> лист.
    На узле-листе-с-детьми — шанс остановиться, иначе углубиться.
    """
    tree = graph.get("classifier", {}).get("tree", []) or []
    weights_cfg = card.get("section_weights", {})
    weights = [float(weights_cfg.get(str(root["g"]), 1)) for root in tree]
    node = rng.choices(tree, weights=weights, k=1)[0]
    while True:
        kids = node.get("children", []) or []
        here = node.get("leaves", []) or []
        if not kids or (here and rng.random() < 0.35):
            code = rng.choice(here)
            break
        node = rng.choice(kids)
    by_code = {leaf["code"]: leaf for leaf in classifier_leaves(graph)}
    return by_code[code]


def generate_card(
    seed: int | None = None,
    overrides: dict[str, Any] | None = None,
    incident_graph: dict[str, Any] | None = None,
    card_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Сгенерировать одну карточку. Детерминировано seed'ом."""
    ov = overrides or {}
    rng = random.Random(seed)
    graph = incident_graph or load_incident_graph()
    card = card_graph or load_card_graph()

    info_prob = float(card.get("info_probability", 0.15))
    leaf: dict[str, Any] | None = None
    info_title: str | None = None
    if ov.get("type"):
        leaf = _resolve_override_leaf(graph, str(ov["type"]))
        if leaf is None and str(ov["type"]) in INFO_TYPES:
            info_title = str(ov["type"])
        if leaf is None and info_title is None:
            raise ValueError(f"unknown type override: {ov['type']!r}")
    elif rng.random() < info_prob:
        info_title = _pick(rng, INFO_TYPES)
    else:
        leaf = _walk_tree_leaf(rng, graph, card)

    if leaf is not None:
        path = list(leaf.get("path", []) or [])
        tags: dict[str, Any] = {
            "attr1": path[0] if len(path) > 0 else "",
            "attr2": path[1] if len(path) > 1 else "",
            "attr3": path[2] if len(path) > 2 else "",
        }
        probs = card.get("flags", {})
        tags["no_access"] = bool(rng.random() < float(probs.get("no_access_probability", 0.2)))
        tags["threat"] = bool(rng.random() < float(probs.get("threat_probability", 0.25)))
        tags["violation"] = bool(rng.random() < float(probs.get("violation_probability", 0.15)))
        tags["medical"] = bool(rng.random() < float(probs.get("medical_probability", 0.3)))
        tags["evac"] = bool(rng.random() < float(probs.get("evac_probability", 0.15)))
        tags["gas"] = bool(rng.random() < float(probs.get("gas_probability", 0.15)))
    else:
        tags = dict(EMPTY_TAGS)

    if "tagDesc" not in ov:
        tags["tagDesc"] = _pick(
            rng, card["narrative"].get("tag_desc_pool", [""])
        )
    elif ov.get("tagDesc"):
        tags["tagDesc"] = ov["tagDesc"]

    addr_cfg = card["address"]
    okrug = ov.get("okrug") or _pick(rng, addr_cfg["okruga"])
    street = ov.get("street") or _pick(rng, addr_cfg["streets"])
    house = str(ov.get("house") or rng.randint(*addr_cfg["house_range"]))
    flat = str(ov.get("flat") or rng.randint(*addr_cfg["flat_range"]))
    entrance = str(rng.randint(*addr_cfg["entrance_range"]))
    floor = str(rng.randint(*addr_cfg["floor_range"]))
    fias = bool(rng.random() < float(addr_cfg.get("fias_probability", 0.0)))
    addr_src = "ФИАС" if fias else "Яндекс.Карты"
    addr_str = f"Москва, {street}, д. {house}, кв. {flat}"
    address_obj = {
        "country": "Россия",
        "subject": "Москва",
        "settlement": "Москва",
        "object": "",
        "okrug": okrug,
        "rayon": "",
        "street": street,
        "house": house,
        "corpus": "",
        "stroenie": "",
        "flat": flat,
        "entrance": entrance,
        "floor": floor,
        "code": "",
        "descr": "",
    }

    caller_cfg = card["caller"]
    if rng.random() < float(caller_cfg.get("foreign_number_probability", 0.0)):
        aon = f"+{rng.randint(370, 999)} {rng.randint(100000, 999999)}"
        foreign_num = True
    else:
        aon = _phone(rng, _pick(rng, caller_cfg["aon_prefixes"]))
        foreign_num = False
    caller_name = ov.get("caller_name") or _pick(rng, caller_cfg["names"])
    caller_status = ov.get("caller_status") or _pick(rng, caller_cfg["statuses"])
    channel = ov.get("channel") or _pick(rng, caller_cfg["channels"])
    foreign_lang = bool(
        rng.random() < float(caller_cfg.get("foreign_lang_probability", 0.0))
    )

    v_cfg = card["victims"]
    if ov.get("victims"):
        victims_val = ov["victims"]
    elif rng.random() < float(v_cfg.get("has_victims_probability", 0.45)):
        victims_val = str(rng.randint(*v_cfg["count_range"]))
    else:
        victims_val = "нет"
    try:
        crowd = int(victims_val) > 5
    except (TypeError, ValueError):
        crowd = False

    if leaf is not None:
        flags = {
            "nd": bool(tags.get("no_access")),
            "ul": bool(tags.get("threat")),
            "pp": victims_val != "нет",
            "violation": bool(tags.get("violation")),
            "victims": victims_val != "нет",
            "gas": bool(tags.get("gas")),
            "threat": bool(tags.get("threat")),
            "medical": bool(tags.get("medical")),
            "evac": bool(tags.get("evac")),
            "crowd": crowd,
        }
        disp = dispatch_for_leaf(graph, leaf, flags)
        inform = informed_for_leaf(graph, leaf, flags)
        services = [service_display_name(graph, gid) for gid in disp]
        services_informed = [service_display_name(graph, gid) for gid in inform]
        if fias:
            services = []  # ФИАС: службы добавляются вручную
            services_informed = []
        what = leaf.get("result") or "Происшествие"
        classifier_code = leaf.get("code")
        classifier_path = path
        incident_category = leaf.get("group") or ""
        main_service = leaf.get("main")
        sections = {s["g"]: s["title"] for s in graph.get("classifier", {}).get("sections", [])}
        classifier_section = {"g": leaf.get("g"), "title": sections.get(leaf.get("g"), "")}
        factors = [f"Признак{i + 1}: {part}" for i, part in enumerate(path)]
        factors += [FLAG_LABELS[k] for k in FLAG_LABELS if tags.get(k)]
        if tags.get("tagDesc"):
            factors.append(tags["tagDesc"])
    else:
        services = []
        services_informed = []
        what = info_title or "Происшествие"
        classifier_code = None
        classifier_path = []
        incident_category = ""
        main_service = None
        classifier_section = None
        factors = []

    victims_phrase = (
        "Пострадавших нет." if victims_val == "нет"
        else f"Пострадавшие: {victims_val}."
    )
    nar = card["narrative"]
    if leaf is not None:
        tpl = _pick(rng, nar["desc_templates_classifier"])
        access_phrase = (
            "Нет доступа." if tags.get("no_access") else "Доступ есть."
        )
        description = tpl.format(
            result=what,
            path=" → ".join(path) if path else what,
            access_phrase=access_phrase,
            victims_phrase=victims_phrase,
        )
    else:
        tpl = _pick(rng, nar["desc_templates_info"])
        description = tpl.format(
            what=what, address=addr_str,
            status=caller_status, victims_phrase=victims_phrase,
        )

    payload = {
        "what": what,
        "classifier_code": classifier_code,
        "classifier_path": classifier_path,
        "classifier_section": classifier_section,
        "incident_category": incident_category,
        "main_service": main_service,
        "address": addr_str,
        "address_obj": address_obj,
        "address_src": addr_src,
        "phones": {"aon": aon, "provided": "", "onsite": ""},
        "phone_foreign": foreign_num,
        "channel": channel,
        "caller_name": caller_name,
        "caller_status": caller_status,
        "caller_foreign_lang": foreign_lang,
        "external_system": "Интеграция ВИС (мок)",
        "victims": victims_val,
        "refusal103": False,
        "factors": factors,
        "tags": tags,
        "services": services,
        "services_informed": services_informed,
        "services_manual": [],
        "services_vis": [],
        "description": description,
        "elapsed_sec": 0,
        "overtime": False,
        "empty": None,
        "links": [],
    }
    trace = [
        f"seed={seed}",
        f"leaf={classifier_code or info_title} {what}",
        f"path={' > '.join(classifier_path) if classifier_path else '-'}",
        f"address={addr_str} [{addr_src}]",
        f"caller={caller_name} ({caller_status}) {aon} {channel}",
        f"victims={victims_val}",
        f"services={len(services)} informed={len(services_informed)}",
    ]
    return {"seed": seed, "payload": payload, "trace": trace}


def timeline_for_card(payload: dict[str, Any]) -> list[dict[str, Any]]:
    card = load_card_graph()
    services_line = (
        ", ".join(s.split(" (")[0] for s in payload.get("services", []))
        or "назначаются диспетчером"
    )
    victims = payload.get("victims", "нет")
    victims_phrase = (
        "Пострадавших нет." if victims == "нет"
        else f"Пострадавшие: {victims}."
    )
    out = []
    for i, tpl in enumerate(card["narrative"]["timeline_templates"], start=1):
        out.append(
            {
                "seq": i,
                "t_sec": (i - 1) * 30,
                "speaker": tpl["speaker"],
                "emotion": tpl["emotion"],
                "text": tpl["text"].format(
                    description=payload.get("description", payload.get("what", "")),
                    address=payload.get("address", ""),
                    victims_phrase=victims_phrase,
                    services_line=services_line,
                ),
            }
        )
    return out
