"""Генератор карточек 112: граф, обход которого = данные карточки.

Анализ страницы /card (frontend/src/pages/Card112.jsx):
  Блоки карточки (по Инструкции_по_заведению_карточки + ТЗ КАРТОЧКА 112):
    1. Телефоны: АОН / предоставленный / на место + канал связи + признак
       зарубежного номера. Канал автоопределяется по префиксу.
    2. Заявитель: ФИО (автокапитализация) + статус (очевидец/пострадавший/...)
       + признак иностранного языка.
    3. Адрес: единая строка + ФИАС/Яндекс подсказки + сетка
       (округ/район/улица/дом/корпус/строение/кв/подъезд/этаж/код) + карта.
       Источник ФИАС => службы вручную (fiasWarn).
    4. Что случилось: тип уровня 1 (51 значение, Таблица 0 ТЗ) -> ТЭГи.
       Ветка fire101 (14 типов): where -> sign -> access -> detail -> place?
       -> threat -> violation -> medical -> evac -> gas -> tagDesc.
       Условия видимости — tagVisibility.js:
         sign пуст/не выбран: только where/sign/access;
         sign=Запах гари: where/sign/access/place/desc (остальное скрыто);
         sign=Пламя + where пуст: только where/sign/access;
         sign=Пламя + where: все ряды, place только при where=Улица.
       Общая ветка generic (37 типов): threat/violation/medical/evac/gas/desc,
       INFO_TYPES (18 типов без выезда): только desc.
    5. Пострадавшие: Нет / Есть(+кол-во).
    6. Описание со слов заявителя (до 1999 симв., первые 100 уходят в 03).
    7. Службы: авто (incidentClassifier.autoServicesFor по group+ТЭГам) +
       ручные + ВИС, минус исключённые; основная подсвечена двойным
       подчёркиванием (isMainService).

Текущий misc/incident_graph.json покрывает ТОЛЬКО блок 4 (дерево
"Что случилось" + flow fire101/generic). Полной карточки из его обхода
не собрать: нет адресов/телефонов/заявителей/пострадавших/служб.

Этот модуль строит ПОЛНЫЙ граф карточки CARD_GRAPH:
  узлы = поля карточки, рёбра = условные переходы (как visibleTagRows),
  обход ROOT -> ... -> LEAF = один валидный payload для
  POST /api/reports/create (+ publish -> scenario для тренажёра).

Узлы графа (порядок обхода = flow):
  type -> [where -> sign -> access -> detail -> place] (только fire101)
       -> threat -> violation -> medical -> evac -> gas -> tagDesc
       -> address -> phones -> applicant -> victims -> description
       -> services (вычисляемый терминальный узел) -> DONE

Использование:
  from misc.card_graph import generate_card, generate_batch, CARD_GRAPH, walk
  card = generate_card(seed=42)            # dict payload карточки
  batch = generate_batch(10, seed=1)       # list[dict]
"""
from __future__ import annotations

import random
from typing import Any

from misc.incident_tree_api import get_type_meta, load_incident_graph

# ---------------------------------------------------------------- pools

OKRUGA = ["ЦАО", "САО", "СВАО", "ВАО", "ЮВАО", "ЮАО", "ЮЗАО", "ЗАО", "СЗАО", "ЗелАО", "ТАО", "НАО"]
STREETS = [
    "Новая Басманная улица", "Тверская улица", "Манежная площадь",
    "Ленинский проспект", "Проспект Вернадского", "Улица Вавилова",
    "Щёлковское шоссе", "Улица 1905 года", "Садовая-Кудринская улица",
]
APPLICANT_STATUSES = ["очевидец", "пострадавший", "родственник", "знакомый", "ребенок", "участник"]
FIRST_NAMES = ["Иван", "Мария", "Алексей", "Ольга", "Дмитрий", "Анна", "Сергей", "Наталья", "Пётр", "Елена"]
LAST_NAMES = ["Иванов", "Петрова", "Смирнов", "Кузнецова", "Соколов", "Морозова", "Попов", "Волкова"]
CHANNELS = ["Теле2", "МТС", "Мегафон", "Билайн", "Городской", "SIP"]
OPERATOR_PREFIX = {"Теле2": "901", "МТС": "915", "Мегафон": "926", "Билайн": "968", "Городской": "495"}

SVC_101 = 'Служба 101 (ГУ МЧС России по г.Москве, ГКУ "Пожарно-спасательный центр" ОДС)'
SVC_102 = 'Служба 102 (Дежурная часть ГУ МВД России по г.Москве)'
SVC_103 = 'Служба 103 (ГБУ города Москвы Станция скорой и неотложной медицинской помощи им.А.С. Пучкова)'
SVC_104 = 'Служба 104 (АО "МОСГАЗ" Диспетчерское управление)'
SVC_JKH = "Деп. ЖКХ (Департамент ЖКХ)"
SVC_CEMP = "ЦЭМП"
SVC_CODD = 'ЦОДД (ГКУ "Центр организации дорожного движения")'
SVC_MOSTRANS = "Мосгортранс"
SVC_MOSBEZ = "Мос.Без. (Московская Безопасность)"

INFO_TYPES = {
    "Отмена вызова", "Ошибочно набран номер", "Тестовый вызов", "Тренировка",
    "Передача дежурства", "Нецелевой вызов", "Консультация",
    "Вызов на иностранном языке", "Справка 101", "Справка 102",
    "Справка 103", "Справка 104", "Справка ГИБДД",
    "Справка Городское хозяйство", "Справка МЧС", "Благодарность службам",
    "Жалоба на действие или бездействие служб",
    "Технический сбой (сбой в работе с оборудованием 112 Москва)",
}

SMELL_SIGN = "Запах гари"
FLAME_SIGN = "Открытое пламя / Дым"

# Описание-шаблоны под ветки (для timeline тренажёра).
DESC_TEMPLATES = {
    "fire101": [
        "Горит {detail} по адресу {addr}, видно открытое пламя, люди {access}.",
        "Дым и запах гари, {detail}, заявитель на месте, доступ: {access}.",
    ],
    "generic": [
        "{title} по адресу {addr}. Заявитель сообщает: требуется помощь.",
        "{title}. Место: {addr}. Угроза людям: {threat}.",
    ],
    "info": [
        "{title}. Выезд служб не требуется, зафиксировать обращение.",
    ],
}

# ---------------------------------------------------------------- graph

# CARD_GRAPH: узел -> {options источник, next функция/имя}.
# options='__dynamic__' означает: варианты вычисляются из контекста обхода
# (как get_next_levels в incident_tree_api). next=None = терминал.
CARD_GRAPH: dict[str, dict[str, Any]] = {
    "ROOT": {"desc": "Старт карточки", "next": "type"},
    "type": {"desc": "Что случилось (51 тип, Таблица 0 ТЗ)", "options": "__incident_types__", "next": "__branch__"},
    "where": {"desc": "Где (fire101)", "options": "__where__", "next": "sign"},
    "sign": {"desc": "Признак пожара", "options": "__sign__", "next": "access"},
    "access": {"desc": "Доступ к людям", "options": "__access__", "next": "detail"},
    "detail": {"desc": "Детализация под where", "options": "__detail__", "next": "place"},
    "place": {"desc": "Место происшествия (только where=Улица + Пламя)", "options": "__place__", "next": "threat"},
    "threat": {"desc": "Угроза людям Да/Нет", "options": "__threat__", "next": "violation"},
    "violation": {"desc": "Правонарушение", "options": "__violation__", "next": "medical"},
    "medical": {"desc": "Медпомощь Да/Нет", "options": "__medical__", "next": "evac"},
    "evac": {"desc": "Эвакуация Да/Нет", "options": "__evac__", "next": "gas"},
    "gas": {"desc": "Газификация", "options": "__gas__", "next": "tagDesc"},
    "tagDesc": {"desc": "Уточнение ТЭГа (свободный ввод)", "options": "__tagdesc__", "next": "address"},
    "address": {"desc": "Адресный блок (округ/улица/дом/...)", "options": "__address__", "next": "phones"},
    "phones": {"desc": "Телефоны + канал", "options": "__phones__", "next": "applicant"},
    "applicant": {"desc": "Заявитель ФИО + статус", "options": "__applicant__", "next": "victims"},
    "victims": {"desc": "Пострадавшие Нет/Есть", "options": "__victims__", "next": "description"},
    "description": {"desc": "Описание со слов заявителя", "options": "__description__", "next": "services"},
    "services": {"desc": "Службы (вычисляются из type+ТЭГов, как autoServicesFor)", "options": "__services__", "next": "DONE"},
    "DONE": {"desc": "Терминал: payload карточки готов"},
}

FIRE101_FLOW = ["where", "sign", "access", "detail", "place", "threat", "violation", "medical", "evac", "gas", "tagDesc"]
GENERIC_FLOW = ["threat", "violation", "medical", "evac", "gas", "tagDesc"]


def _detail_pool(where: str, tag_sets: dict) -> list[str]:
    return {
        "Транспорт": tag_sets.get("transport_detail", []),
        "Дом": tag_sets.get("house_detail", []),
        "Здание / объект": tag_sets.get("object_detail", []),
        "Опасный объект": tag_sets.get("hazard_detail", []),
    }.get(where, tag_sets.get("street_detail", []))


def visible_rows(kind: str, title: str, tags: dict) -> list[str]:
    """Питон-порт visibleTagRows (frontend/src/lib/tagVisibility.js)."""
    if kind == "fire101":
        sign = tags.get("sign", "")
        if sign == SMELL_SIGN:
            rows = ["where", "sign", "access", "place"]
        elif sign == FLAME_SIGN:
            if not tags.get("where"):
                return ["where", "sign", "access"]
            rows = list(FIRE101_FLOW[:-1])  # без tagDesc
        else:
            return ["where", "sign", "access"]
        if tags.get("where") != "Улица":
            rows = [r for r in rows if r != "place"]
        return rows
    if title in INFO_TYPES:
        return []
    return list(GENERIC_FLOW[:-1])


def auto_services(group: str | None, tags: dict, fias_manual: bool = False) -> list[str]:
    """Питон-порт autoServicesFor (incidentClassifier.js) + правила Card112."""
    if fias_manual:
        return []
    title = tags.get("__title__", "")
    if title in INFO_TYPES:
        return []
    out: list[str] = []
    if group == "101":
        out.append(SVC_101)
    elif group == "102":
        out.append(SVC_102)
    elif group == "103":
        out += [SVC_103, SVC_CEMP]
    elif group == "104":
        out.append(SVC_JKH)
    flat = " ".join(v for v in tags.values() if v)
    transport_kw = ("Транспорт", "Общественный", "Автомашина", "Метро", "Мост", "Тоннель", "Эстакада", "МЦК", "Ж/Д", "Вокзал", "Аэропорт", "ДТП с пожаром")
    if any(k in flat for k in transport_kw):
        out += [SVC_CODD, SVC_MOSTRANS]
    if any(k in flat for k in ("Мусор", "Парк", "Лес", "Торф", "Трава", "Дерево", "ЛЭП", "Провода", "Мачта", "Опора")):
        out.append(SVC_JKH)
    if tags.get("threat") == "Да" or tags.get("medical") == "Да":
        if SVC_CEMP not in out:
            out.append(SVC_CEMP)
    if tags.get("violation") in ("Да", "Есть", "Есть правонарушение"):
        if SVC_102 not in out:
            out.append(SVC_102)
    if tags.get("evac") == "Да" and SVC_MOSBEZ not in out:
        out.append(SVC_MOSBEZ)
    if tags.get("gas") == "Да" and SVC_104 not in out:
        out.append(SVC_104)
    if tags.get("sign") == SMELL_SIGN:  # как в Card112: запах гари режет 102/104
        out = [s for s in out if s not in (SVC_102, SVC_104)]
    seen, res = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            res.append(s)
    return res


def next_options(node: str, ctx: dict, graph_data: dict | None = None) -> list[str]:
    """Варианты ребра из узла при текущем контексте обхода (ctx)."""
    g = graph_data or load_incident_graph()
    tag_sets = g.get("tag_sets", {})
    tags = ctx.get("tags", {})
    kind = ctx.get("kind", "generic")
    title = ctx.get("type", "")
    if node == "type":
        return list(g.get("root_children", []))
    if node == "where":
        return list(tag_sets.get("where", []))
    if node == "sign":
        return list(tag_sets.get("sign", []))
    if node == "access":
        return list(tag_sets.get("access", []))
    if node == "detail":
        return list(_detail_pool(tags.get("where", ""), tag_sets))
    if node == "place":
        if kind == "fire101" and tags.get("sign") == FLAME_SIGN and tags.get("where") == "Улица":
            return list(tag_sets.get("place", []))
        return []
    if node in ("threat", "medical", "evac"):
        return list(tag_sets.get("threat" if node == "threat" else node, ["Да", "Нет"]))
    if node == "violation":
        if kind == "fire101":
            return ["Да", "Нет"]
        return ["Есть правонарушение"]
    if node == "gas":
        return list(tag_sets.get("gas", ["Да", "Нет", "Нет данных"]))
    if node == "tagDesc":
        return [""]  # свободный ввод; генератор ставит "" или уточнение
    # Параллельные ветки — одно ребро "заполнить блок" (детали — вサンプラх ниже)
    if node in ("address", "phones", "applicant", "victims", "description", "services"):
        return ["fill"]
    if node == "ROOT":
        return ["type"]
    return []


def next_node(node: str, ctx: dict) -> str | None:
    """Следующий узел обхода с учётом условных рёбер (видимости ТЭГов)."""
    tags = ctx.get("tags", {})
    kind = ctx.get("kind", "generic")
    title = ctx.get("type", "")
    if node == "ROOT":
        return "type"
    if node == "type":
        if title in INFO_TYPES:
            return "tagDesc"
        return "where" if kind == "fire101" else "threat"
    if kind == "fire101":
        order = ["where", "sign", "access", "detail", "place", "threat",
                 "violation", "medical", "evac", "gas", "tagDesc", "address",
                 "phones", "applicant", "victims", "description", "services"]
    elif title in INFO_TYPES:
        order = ["tagDesc", "address", "phones", "applicant", "victims", "description", "services"]
    else:
        order = ["threat", "violation", "medical", "evac", "gas", "tagDesc",
                 "address", "phones", "applicant", "victims", "description", "services"]
    if node not in order:
        return None
    idx = order.index(node)
    # пропуск скрытых ТЭГ-узлов
    vis = set(visible_rows(kind, title, tags)) | {"tagDesc", "address", "phones",
                                                  "applicant", "victims", "description", "services"}
    for nxt in order[idx + 1:]:
        if nxt in vis or nxt in ("address", "phones", "applicant", "victims", "description", "services", "tagDesc"):
            # place уже отфильтрован через vis; tagDesc виден всегда
            if nxt in ("where", "sign", "access", "detail", "place", "threat",
                       "violation", "medical", "evac", "gas") and nxt not in vis:
                continue
            return nxt
    return "DONE" if node != "services" else "DONE"


def walk(seed: int | None = None, fixed_type: str | None = None) -> dict:
    """Случайный обход графа: возвращает ctx {path, tags, ...}.

    path — полный путь обхода (узел=значение), tags — ТЭГи карточки.
    """
    rng = random.Random(seed)
    g = load_incident_graph()
    ctx: dict = {"tags": {}, "path": []}
    # --- узел type
    types = next_options("type", ctx, g)
    title = fixed_type if fixed_type in types else rng.choice(types)
    meta = get_type_meta(g, title) or {}
    ctx["type"] = title
    ctx["groups"] = list(meta.get("groups", []))
    ctx["group"] = ctx["groups"][0] if ctx["groups"] else "101"
    ctx["kind"] = meta.get("kind", "generic")
    ctx["path"].append(("type", title))
    # --- ТЭГ-ветка условным обходом
    node = next_node("type", ctx)
    while node not in (None, "DONE", "address", "phones", "applicant", "victims", "description", "services"):
        opts = next_options(node, ctx, g)
        if not opts:
            node = next_node(node, ctx)
            continue
        # place необязателен (только для Улицы) — берём с p=0.5
        if node == "place" and rng.random() < 0.5:
            node = next_node(node, ctx)
            continue
        val = rng.choice(opts)
        # violation fire101: фронт даёт Да/Нет, Нет = сброс
        if node == "violation" and ctx["kind"] == "fire101" and val == "Нет":
            val = ""
        if val:
            ctx["tags"][node] = val
            ctx["path"].append((node, val))
        node = next_node(node, ctx)
        # sign определяет видимость хвоста: после sign/access обход сам
        # перепрыгнет скрытые узлы через next_node
    ctx["tags"]["tagDesc"] = ""
    # --- параллельные блоки
    okrug = rng.choice(OKRUGA)
    street = rng.choice(STREETS)
    house = str(rng.randint(1, 60))
    ctx["address"] = {
        "country": "Россия", "subject": "Москва", "settlement": "Москва",
        "object": "", "okrug": okrug, "rayon": "", "street": street,
        "house": house, "corpus": "", "stroenie": str(rng.choice(["", "", "1"])),
        "flat": str(rng.randint(1, 200)) if rng.random() < 0.4 else "",
        "entrance": str(rng.randint(1, 8)) if rng.random() < 0.4 else "",
        "floor": str(rng.randint(1, 17)) if rng.random() < 0.3 else "",
        "code": "", "descr": "",
    }
    ctx["address_str"] = f"Москва, {street}, {house}"
    channel = rng.choice(CHANNELS)
    prefix = OPERATOR_PREFIX.get(channel, "915")
    aon = f"+7 ({prefix}) {rng.randint(100,999):03d}-{rng.randint(10,99):02d}-{rng.randint(10,99):02d}"
    ctx["phones"] = {"aon": aon, "provided": aon if rng.random() < 0.7 else "",
                     "onsite": "" if rng.random() < 0.7 else aon}
    ctx["channel"] = channel
    ctx["applicant"] = f"{rng.choice(LAST_NAMES)} {rng.choice(FIRST_NAMES)}"
    ctx["applicant_status"] = rng.choice(APPLICANT_STATUSES)
    if rng.random() < 0.2:
        ctx["victims"] = {"count": str(rng.randint(1, 3)), "label": "Есть"}
    else:
        ctx["victims"] = {"count": "", "label": "Нет"}
    detail = ctx["tags"].get("detail", "")
    access = ctx["tags"].get("access", "неизвестно")
    threat = ctx["tags"].get("threat", "Нет")
    addr = ctx["address_str"]
    if ctx["kind"] == "fire101":
        tpl = rng.choice(DESC_TEMPLATES["fire101"])
        desc = tpl.format(detail=detail or "возгорание", addr=addr, access=access)
    elif ctx["type"] in INFO_TYPES:
        desc = rng.choice(DESC_TEMPLATES["info"]).format(title=title)
    else:
        desc = rng.choice(DESC_TEMPLATES["generic"]).format(title=title, addr=addr, threat=threat)
    ctx["description"] = desc
    ctx["services"] = auto_services(ctx["group"], {**ctx["tags"], "__title__": ctx["type"]}, fias_manual=False)
    # фиксируем полный путь параллельных блоков
    for n in ("address", "phones", "applicant", "victims", "description", "services"):
        ctx["path"].append((n, "fill"))
    ctx["path"].append(("DONE", ""))
    return ctx


def to_report_payload(ctx: dict, user_id: str | None = None) -> dict:
    """Контекст обхода -> payload POST /api/reports/create (формат Card112.doSave)."""
    tags = dict(ctx.get("tags", {}))
    factors = [f"{k}:{v}" for k, v in tags.items() if v]
    addr = ctx.get("address", {})
    return {
        "user_id": user_id,
        "what": ctx.get("type", ""),
        "incident_category": ctx.get("group", "101"),
        "incident_kind": ctx.get("kind", "generic"),
        "address": ctx.get("address_str", ""),
        "address_obj": addr,
        "address_src": "Генератор карточек (мок)",
        "phones": ctx.get("phones", {}),
        "phone_foreign": False,
        "channel": ctx.get("channel", ""),
        "caller_name": ctx.get("applicant", ""),
        "caller_status": ctx.get("applicant_status", ""),
        "caller_foreign_lang": False,
        "external_system": "Генератор карточек",
        "victims": ctx["victims"]["count"] if ctx.get("victims", {}).get("label") == "Есть" else "нет",
        "factors": factors,
        "tags": tags,
        "services": list(ctx.get("services", [])),
        "services_manual": [],
        "services_vis": [],
        "description": ctx.get("description", ""),
        "elapsed_sec": 0,
        "overtime": False,
        "empty": None,
        "links": [],
        "path": [list(p) for p in ctx.get("path", [])],  # след обхода для отладки
    }


def generate_card(seed: int | None = None, incident_type: str | None = None,
                  user_id: str | None = None) -> dict:
    """Одна карточка: обход графа -> готовый payload."""
    return to_report_payload(walk(seed=seed, fixed_type=incident_type), user_id=user_id)


def generate_batch(count: int = 5, seed: int | None = None,
                   incident_type: str | None = None) -> list[dict]:
    """Пакет карточек: детерминирован при заданном seed."""
    rng = random.Random(seed)
    return [generate_card(seed=rng.randint(0, 2 ** 31 - 1),
                          incident_type=incident_type) for _ in range(count)]


def describe_graph() -> dict:
    """Машиночитаемая схема графа для фронта/документации."""
    return {
        "nodes": {k: v.get("desc", "") for k, v in CARD_GRAPH.items()},
        "flows": {"fire101": FIRE101_FLOW, "generic": GENERIC_FLOW,
                  "info": ["tagDesc"]},
        "edges": "next_node(ctx): условные переходы по visible_rows; "
                 "services — терминальный вычисляемый узел (auto_services)",
    }
