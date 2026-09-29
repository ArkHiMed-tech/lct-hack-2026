"""Сборка misc/incident_graph.json v2 из Excel-классификатора происшествий.

Источник: /workspace/Классификатор_*.xlsx, лист Лист1:
  дерево Г -> Группа -> Признак1 -> Признак2 -> Признак3 -> лист
  (Номер, Итоговый тип, ТИП ЕКП35, Главная служба, доп. признаки
  + диспетчеризация по сервисным колонкам).

Что делает:
  1. Парсит 509 строк-листьев (разделы 1-9; разделы 10-23 пустые).
  2. Снимает диспетчеризацию: сервисные колонки -> {service_id: значение}.
     Условные колонки (признаки НД/УЛ/ПП, Правонарушение/Пострадавшие,
     газификация, тоннель/пеш/ав, перекрытие и т.д.) сохраняются как
     варианты выбора по флагам карточки.
  3. Сохраняет обратно-совместимые ключи v1 (root_children/type_meta/
     children/tag_sets/flow) без изменений и добавляет секцию "classifier".

Запуск:  python3 misc/build_incident_graph.py [--check]
  --check  только сверить xlsx с текущим json (без записи).

Пересборка детерминирована: сортировки фиксированы, json с sort_keys.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from pathlib import Path

_MISC_DIR = Path(__file__).resolve().parent
GRAPH_PATH = _MISC_DIR / "incident_graph.json"

# col_idx -> (variant_id, service_group_id, flag)
SERVICE_COLUMNS: dict[int, tuple[str, str, str | None]] = {
    13: ("mchs101", "mchs101", None),
    14: ("mchs101_nd", "mchs101", "nd"),
    15: ("odps", "odps", None),
    16: ("odps_ul", "odps", "ul"),
    17: ("odps_pp", "odps", "pp"),
    18: ("odps_nd", "odps", "nd"),
    19: ("mgpss", "mgpss", None),
    20: ("mvd", "mvd", None),
    21: ("mvd_viol", "mvd", "violation"),
    22: ("mvd_vict", "mvd", "victims"),
    23: ("smp", "smp", None),
    24: ("smp_vict", "smp", "victims"),
    25: ("smp_vict_absent", "smp", "victims_absent"),
    26: ("mosgaz", "mosgaz", None),
    27: ("mosgaz_gas", "mosgaz", "gas"),
    28: ("cemp", "cemp", None),
    29: ("cemp_threat", "cemp", "threat"),
    30: ("cemp_vict", "cemp", "victims"),
    31: ("cemp_med", "cemp", "medical"),
    32: ("cemp_evac", "cemp", "evac"),
    33: ("fsb", "fsb", None),
    34: ("fsb_crowd", "fsb", "crowd"),
    35: ("moblgaz", "moblgaz", None),
    36: ("avtodor", "avtodor", None),
    37: ("mostrans", "mostrans", None),
    38: ("mostrans_vict", "mostrans", "victims"),
    39: ("mostrans_block", "mostrans", "block"),
    40: ("gorhoz", "gorhoz", None),
    41: ("gormost", "gormost", None),
    42: ("gormost_tunnel", "gormost", "tunnel"),
    43: ("gormost_pesh", "gormost", "pesh"),
    44: ("gormost_av", "gormost", "av"),
    45: ("kanal", "kanal", None),
    46: ("mgts", "mgts", None),
    47: ("mgts_sites", "mgts", "sites"),
    48: ("metro", "metro", None),
    49: ("vodokanal", "vodokanal", None),
    50: ("moek", "moek", None),
    51: ("moesk", "moesk", None),
    52: ("oek", "oek", None),
    53: ("moslift", "moslift", None),
    54: ("codd", "codd", None),
    55: ("depgkh", "depgkh", None),
    56: ("mosbez", "mosbez", None),
    57: ("mkp", "mkp", None),
    58: ("apperat", "apperat", None),
    59: ("moskollektor", "moskollektor", None),
    60: ("rzd", "rzd", None),
    61: ("depobr", "depobr", None),
    62: ("crvh", "crvh", None),
    63: ("voenkom", "voenkom", None),
    64: ("oati", "oati", None),
    65: ("vodostok", "vodostok", None),
    66: ("dppios", "dppios", None),
    67: ("tszn", "tszn", None),
    68: ("rsvo", "rsvo", None),
    69: ("evazd", "evazd", None),
    70: ("msppn", "msppn", None),
    71: ("dtu_r", "dtu_r", None),
    72: ("dtu", "dtu", None),
    73: ("rosgvard", "rosgvard", None),
    74: ("terr_oiv", "terr_oiv", None),
    75: ("terr_oiv_tinao", "terr_oiv_tinao", None),
    76: ("avtodor_ao", "avtodor_ao", None),
    77: ("depstroy", "depstroy", None),
    78: ("depstroy_stroyka", "depstroy", "stroyka"),
    79: ("komvet", "komvet", None),
    80: ("moszhil", "moszhil", None),
    81: ("depkult", "depkult", None),
    82: ("csa", "csa", None),
    83: ("ntu", "ntu", None),
    84: ("fso", "fso", None),
    85: ("gupmsr", "gupmsr", None),
    86: ("gupmsr_pozhar", "gupmsr", "pozhar"),
    87: ("komtur", "komtur", None),
    88: ("dgp", "dgp", None),
    89: ("arm112", "arm112", None),
    90: ("cukb", "cukb", None),
    91: ("cukb_bpla", "cukb_bpla", None),
    92: ("orgperevoz", "orgperevoz", None),
    93: ("orgperevoz_block", "orgperevoz", "block"),
    94: ("mosekom", "mosekom", None),
    95: ("rhbz", "rhbz", None),
    96: ("rhbz_moscow", "rhbz", "moscow"),
    97: ("sitien", "sitien", None),
    98: ("depgrstroy", "depgrstroy", None),
}

# service_group_id -> (заголовок из xlsx, имя в serviceCatalog.js | None)
SERVICE_META: dict[str, tuple[str, str | None]] = {
    "mchs101": ("Служба 101", "Служба 101 (ГУ МЧС России по г.Москве, ГКУ \"Пожарно-спасательный центр\" ОДС)"),
    "odps": ("ОДС ПСЦ", None),
    "mgpss": ("МГПСС", None),
    "mvd": ("Классификатор МВД", "Служба 102 (Дежурная часть ГУ МВД России по г.Москве)"),
    "smp": ("Классификатор СМП", "Служба 103 (ГБУ города Москвы Станция скорой и неотложной медицинской помощи им.А.С. Пучкова)"),
    "mosgaz": ("Классификатор МОСГАЗ", "Служба 104 (АО \"МОСГАЗ\" Диспетчерское управление)"),
    "cemp": ("ЦЭМП", "ЦЭМП"),
    "fsb": ("Классификатор ФСБ", "ФСБ"),
    "moblgaz": ("Классификатор Мособлгаз", "Мособлгаз"),
    "avtodor": ("Автомобильные дороги", "Автодороги"),
    "mostrans": ("Мосгортранс", "Мосгортранс"),
    "gorhoz": ("Гор. Хозяйство", None),
    "gormost": ("ГОРМОСТ", "Гормост (Гормост)"),
    "kanal": ("Канал имени Москвы", "Канал им. Москвы (ФГБУ «Канал имени Москвы»)"),
    "mgts": ("МГТС", "МГТС (Московская городская телефонная сеть)"),
    "metro": ("Метро", "Метро"),
    "vodokanal": ("Мосводоканал", "Мосводоканал (АО \"Мосводоканал\")"),
    "moek": ("МОЭК", "МОЭК"),
    "moesk": ("МОЭСК (Россети)", "Россети МР"),
    "oek": ("ОЭК", "ОЭК (Объединенная энергетическая компания)"),
    "moslift": ("Мослифт", "Мослифт (Лифт МСК)"),
    "codd": ("ЦОДД", "ЦОДД (ГКУ \"Центр организации дорожного движения\")"),
    "depgkh": ("Деп. ЖКХ", "Деп. ЖКХ (Департамент ЖКХ)"),
    "mosbez": ("Департамент РБиПК (ГКУ МОСБЕЗ)", "Мос.Без. (Московская Безопасность)"),
    "mkp": ("МКП, Аналитика", None),
    "apperat": ("Аппарат МЭРА", None),
    "moskollektor": ("Москоллектор", "Москоллектор (Москоллектор)"),
    "rzd": ("РЖД", "МЖД (Московская железная дорога)"),
    "depobr": ("Департамент образования", "Деп. Обр. (Московский Департамент Образования)"),
    "crvh": ("Центррегионводхоз", "Центррегионводхоз (Центррегионводхоз)"),
    "voenkom": ("Военная комендатура", "Воен. комендатура (Воен. комендатура)"),
    "oati": ("ОАТИ", "ОАТИ (Объединение Административно-Технических Инспекций города Москвы)"),
    "vodostok": ("Мосводосток", "Мосводосток (Мосводосток)"),
    "dppios": ("Департамент ППиООС", "Деп. природопользования (Департамент природопользования и охраны окружающей среды города Москвы)"),
    "tszn": ("ОД Департамент ТСЗН", "Деп. труда и соц.защиты (Департамент труда и социальной защиты населения города Москвы)"),
    "rsvo": ("РСВО", "ФГУП РСВО (Российские сети вещания и оповещения)"),
    "evazd": ("ЭВАЖД", "ЭВАЖД (ГБУ «Учреждение по эксплуатации высотных административных и жилых домов»)"),
    "msppn": ("МСППН", "ГБУ МСППН (Московская служба психологической помощи населению ГБУ города Москвы)"),
    "dtu_r": ("ДТУ_Р (Ритуал)", None),
    "dtu": ("ДТУ", "Дежурно-диспетчерская служба (Дежурно-диспетчерская служба)"),
    "rosgvard": ("Росгвардия", None),
    "terr_oiv": ("Территориальные ОИВ", None),
    "terr_oiv_tinao": ("Территориальные ОИВ ТиНАО", None),
    "avtodor_ao": ("Автомобильные дороги АО", None),
    "depstroy": ("Департамент строительства", "Департамент строительства (Департамент строительства)"),
    "komvet": ("Комитет ветеринарии", "Комитет ветеринарии (Комитет ветеринарии города Москвы)"),
    "moszhil": ("Мосжилинспекция", "Мосжилинспекция (Государственная жилищная инспекция города Москвы)"),
    "depkult": ("Департамент культуры", "Департамент культуры города Москвы (Департамент культуры города Москвы)"),
    "csa": ("ГКУ ЦСА им. Глинки", "ГКУ ЦСА (Центр социальной помощи)"),
    "ntu": ("ГКУ НТУ", None),
    "fso": ("ФСО", None),
    "gupmsr": ("ГУП МСР", None),
    "komtur": ("Комитет по туризму", "Мостуризм (Комитет по туризму города Москвы)"),
    "dgp": ("ДГП", None),
    "arm112": ("АРМ-112", None),
    "cukb": ("ЦУКБ Министерство обороны", None),
    "cukb_bpla": ("ЦУКБ.БПЛА Министерство обороны", None),
    "orgperevoz": ("ГКУ Организатор перевозок", None),
    "mosekom": ("ГПБУ Мосэкомониторинг", None),
    "rhbz": ("Министерство обороны РХБЗ", None),
    "sitien": ("ООО Ситиэнерго", None),
    "depgrstroy": ("Департамент гражданского строительства", None),
}

FLAGS = {
    "nd": "Нет доступа (признак НД)",
    "ul": "Угроза людям (признак УЛ)",
    "pp": "Пострадавшие/погибшие (признак ПП)",
    "violation": "Правонарушение",
    "victims": "Пострадавшие",
    "victims_absent": "Пострадавшие не на месте",
    "gas": "Газификация",
    "threat": "Угроза людям (ЦЭМП)",
    "medical": "Мед. помощь (ЦЭМП)",
    "evac": "Треб. эвакуация (ЦЭМП)",
    "crowd": ">5 чел / ОД (ФСБ)",
    "block": "Перекрытие движения",
    "tunnel": "Тоннель (ГОРМОСТ)",
    "pesh": "Пешеходный переход (ГОРМОСТ)",
    "av": "Аварийный участок (ГОРМОСТ)",
    "sites": "На объектах связи (МГТС)",
    "stroyka": "Стройка (Депстрой)",
    "pozhar": "Пожары (ГУП МСР)",
    "moscow": "Москва (РХБЗ)",
}

NO_RESPONSE = "нет реагирования"
HIDDEN_P1 = "Не отображается оператору 112"

# Связь корней операторского выбора (v1) с разделами классификатора.
# Разделы 10-23 в xlsx пустые -> покрытие остаётся рукотворным (v1), root_map пуст.
ROOT_MAP: dict[str, dict] = {
    "101": {"g": [1]},
    "102": {"services_any": ["mvd"]},
    "103": {"services_any": ["smp", "cemp"]},
    "104": {"services_any": ["mosgaz"]},
    "ДТП": {"g": [2]},
    "Взрыв": {"g": [3]},
    "Угроза взрыва/террористического акта": {"g": [4, 5]},
    "Угроза обрушения": {"g": [6]},
    "Обрушение": {"g": [6]},
    "БПЛА": {"services_any": ["fsb", "rosgvard"]},
    "Природная стихия": {"g": [7], "groups": ["Природная стихия"]},
    "Скопление воды": {"g": [7], "groups": ["Скопление воды Подтопление Паводок"]},
    "Экологическое происшествие": {"g": [8]},
    "Аварии на гидротехнических сооружениях": {"g": [9]},
    "Аварии и происшествия на транспортных объектах": {"g": [1, 2], "groups": ["горит транспорт", "Дорожно-транспортные происшествия без пострадавших", "Дорожно-транспортные происшествия с пострадавшими"]},
    "Аварии и происшествия в городском хозяйстве": {"services_any": ["gorhoz", "depgkh", "vodokanal", "moek", "oek"]},
    "Аварии на опасных и производственных объектах": {"g": [1], "groups": ["пожар-опасный объект"]},
    "Человек в опасности": {"services_any": ["smp", "mvd"]},
    "Ребенок в опасности": {"services_any": ["smp", "mvd"]},
    "Смертельный исход": {"services_any": ["mvd"]},
}


def _clean(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def find_xlsx() -> Path:
    env = os.getenv("CLASSIFIER_XLSX", "")
    if env and Path(env).exists():
        return Path(env)
    found = sorted(
        glob.glob("/workspace/Классификатор_*.xlsx"),
        key=lambda p: os.path.getmtime(p),
    )
    if not found:
        raise FileNotFoundError("Excel-классификатор не найден в /workspace")
    return Path(found[-1])


def parse_xlsx(path: Path):
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Лист1"]
    rows = list(ws.iter_rows(values_only=True))

    sections: dict[int, str] = {}
    for row in rows[3:]:
        code, title = row[4], _clean(row[5])
        if code is not None and len(str(code)) <= 2 and title:
            sections[int(code)] = title

    leaves = []
    last_group: str | None = None
    for row in rows[3:]:
        code = row[4]
        if code is None or len(str(code)) != 7:
            continue
        group = _clean(row[5]) or last_group
        last_group = _clean(row[5]) or last_group
        g, p1, p2, p3 = row[0], _clean(row[6]), _clean(row[7]), _clean(row[8])
        path_parts = [p for p in (p1, p2, p3) if p]
        dispatch: dict[str, str] = {}
        for col, (sid, _gid, _flag) in SERVICE_COLUMNS.items():
            if col < len(row):
                val = _clean(row[col])
                if val:
                    dispatch[sid] = val
        leaves.append(
            {
                "code": str(code),
                "g": int(g),
                "group": group,
                "path": path_parts,
                "operator_visible": p1 != HIDDEN_P1,
                "result": _clean(row[10]),
                "ekp35": _clean(row[11]),
                "main": _clean(row[12]),
                "extra": _clean(row[9]),
                "dispatch": dispatch,
            }
        )
    return sections, leaves


def build_graph(sections: dict[int, str], leaves: list[dict], prev: dict, source: str) -> dict:
    service_ids = sorted({gid for _, gid, _ in SERVICE_COLUMNS.values()})
    services = []
    for gid in service_ids:
        cols = sorted(c for c, (_, g2, _) in SERVICE_COLUMNS.items() if g2 == gid)
        variants = [
            {"column": c, "variant": SERVICE_COLUMNS[c][0], "flag": SERVICE_COLUMNS[c][2]}
            for c in cols
        ]
        title, catalog = SERVICE_META[gid]
        services.append(
            {"id": gid, "title": title, "catalog": catalog, "columns": variants}
        )

    filled = sorted({leaf["g"] for leaf in leaves})
    sections_out = [
        {"g": num, "title": title, "filled": num in filled}
        for num, title in sorted(sections.items())
    ]

    return {
        "version": 2,
        "source": source,
        "root": prev.get("root", "112"),
        "root_children": prev["root_children"],
        "type_meta": prev["type_meta"],
        "tag_sets": prev["tag_sets"],
        "children": prev["children"],
        "flow": prev["flow"],
        "classifier": {
            "sections": sections_out,
            "flags": FLAGS,
            "services": services,
            "leaf_count": len(leaves),
            "hidden_leaf_count": sum(1 for leaf in leaves if not leaf["operator_visible"]),
            "leaves": sorted(leaves, key=lambda leaf: leaf["code"]),
            "root_map": ROOT_MAP,
            "no_response_marker": NO_RESPONSE,
        },
    }


def main() -> int:
    check_only = "--check" in sys.argv
    xlsx = find_xlsx()
    print(f"xlsx: {xlsx}")
    sections, leaves = parse_xlsx(xlsx)
    print(f"sections: {len(sections)}, leaves: {len(leaves)}")
    codes = [leaf["code"] for leaf in leaves]
    assert len(set(codes)) == len(codes), "дублирующиеся Номера!"
    assert all(leaf["path"] for leaf in leaves), "лист без пути!"

    with open(GRAPH_PATH, encoding="utf-8") as fh:
        prev = json.load(fh)
    graph = build_graph(sections, leaves, prev, f"{xlsx.name} ({len(leaves)} листьев)")

    if check_only:
        cur = prev.get("classifier", {})
        print(f"текущий json: version={prev.get('version')}, leaves={cur.get('leaf_count')}")
        print("check: OK" if cur.get("leaf_count") == len(leaves) else "check: РАСХОЖДЕНИЕ")
        return 0

    with open(GRAPH_PATH, "w", encoding="utf-8") as fh:
        json.dump(graph, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")
    size_kb = GRAPH_PATH.stat().st_size // 1024
    print(f"записано: {GRAPH_PATH} ({size_kb} КБ)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
