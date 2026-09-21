# JSON-контракт обмена с бэкендом (FastAPI, изолированный контур)

Контракт данных между фронтендом и бэкендом, приведён в соответствие с `PLAN.md`
(2026-09-19) и папкой `/workspace/TZ` (ТЗ финал 01.09.2026, Инструкция по заведению
карточки, Памятка АРМ-112 для ДДС, Классификатор v046 ×2, Билеты-задачи, datasheet РТУ Т16Р).
Бэкенд — авторитетный расчёт оценки; фронт только отображает (черновая оценка на фронте
допустима для `ChecklistProgress`). Внутренний API — только для собственных модулей,
внешних интеграций нет. СУБД — PostgreSQL 12+ (SQLite/`public/data/*.json` — только сид
прототипа с переездом в БД при старте). Время — ISO 8601 UTC.

## Схема файлов каталога

```
config.json                 — пути к файлам, пороги оценок, глобальные настройки
users.json                  — пользователи и роли
roles.json                  — доступные роли
services.json               — справочник экстренных служб
scenarios/
  catalog.json              — список сценариев (краткая карточка)
  <scenario_id>.json        — сценарий во всех деталях
rubrics/
  <rubric_id>.json          — чек-лист/рубрика оценивания
results/
  <session_id>.json         — результат одной тренировки
```

## 1. `config.json`

```json
{
  "schema_version": 2,
  "scenarios_path": "scenarios/catalog.json",
  "users_path": "users.json",
  "results_path": "results",
  "rubrics_path": "rubrics",
  "sla_answer_sec": 8,
  "sla_card_sec": 30,
  "score_group_weights": { "A": 0.10, "B": 0.20, "C": 0.25, "D": 0.20, "E": 0.10, "F": 0.15 },
  "verdicts": { "excellent_min": 80, "pass_min": 60 },
  "voice_max_latency_ms": 150,
  "session_survive_sec": 30,
  "max_parallel_sessions": 20,
  "backup_period": "daily",
  "audit_retention_months": 6
}
```

Нормы из PLAN §3–4 / ТЗ: `sla_answer_sec` 8–10 (дефолт сценария 8), `sla_card_sec`
дефолт 30 (настраивается преподавателем); веса групп A 0.10 / B 0.20 / C 0.25 / D 0.20 /
E 0.10 / F 0.15; вердикты ≥ 80 отлично, 60–79 зачтено, < 60 или любая X-критика — не зачтено.

## 2. `roles.json`, `users.json`

```json
// roles.json
[ { "id": "student", "title": "Обучающийся" },
  { "id": "teacher", "title": "Преподаватель" },
  { "id": "admin",  "title": "Администратор" } ]
```

```json
// users.json — профиль локального контура (аутентификация при каждом входе,
// автовыход при простое ~24 ч, TLS внутри контура, аудит; номер АРМ — по Инструкции)
[ { "id": "u-001", "login": "umc_operdds1", "name": "Иванова Мария Петровна", "role": "student",
    "post": "Оператор ДДС", "arm_number": "АРМ 4",
    "group": "Группа 1", "last_name": "Иванова", "active": true } ]
```

## 3. `services.json` (справочник служб: экстренные + профильные ДДС Москвы)

```json
[ { "id": "fire",       "title": "Пожарно-спасательная",    "phone": "101", "code": "01" },
  { "id": "ambulance",  "title": "Скорая медицинская",      "phone": "103", "code": "03" },
  { "id": "police",     "title": "Полиция",                 "phone": "102", "code": "02" },
  { "id": "gas",        "title": "Аварийная газовая",       "phone": "104", "code": "04" },
  { "id": "utility",    "title": "Аварийная городская",     "phone": "105", "code": "05" },
  { "id": "gormost",    "title": "Гормост",                 "phone": null,  "code": null },
  { "id": "housing",    "title": "Жилищные службы",         "phone": null,  "code": null },
  { "id": "mosvodokanal", "title": "Мосводоканал",          "phone": null,  "code": null },
  { "id": "moscollector", "title": "Москоллектор",          "phone": null,  "code": null },
  { "id": "uprava",      "title": "Управы",                 "phone": null,  "code": null } ]
```

Расширен по PLAN §3 (Блок 3) и сценарию ролевой фильтрации ТЗ: в ленту обучающегося
попадают только профильные события. ТЭГи сценария → автослужбы + ручное добавление.
При адресе ФИАС службы не подтягиваются — добавляются вручную (Инструкция).

## 4. `scenarios/catalog.json`

```json
[ { "id": "scn-001", "title": "Пожар в многоквартирном доме", "category": "fire",
    "classifier_code": "101",
    "difficulty": "medium", "severity": "high", "rubric_id": "rubric-112-base",
    "assigned_groups": ["Группа 1"],
    "source": "generated",
    "validation": "validated",
    "done": true, "best_score": 82, "estimate_sec": 240,
    "sla_answer_sec": 8, "sla_card_sec": 30 } ]
```

`category` — из Классификатора v046 (~50 типов: 101/102/103/104, ДТП, пожары, медицина,
газ, городское хозяйство и пр.; Билеты-задачи С112 — второй источник).
`source`: `generated` / `manual` / `mixed`. `validation`: `draft` / `validated` / `rejected`.

## 5. `scenarios/<scenario_id>.json`

```json
{
  "id": "scn-001",
  "title": "Пожар в многоквартирном доме",
  "category": "fire",
  "classifier_code": "101",
  "difficulty": "medium",
  "severity": "high",
  "rubric_id": "rubric-112-base",
  "sla_answer_sec": 8,
  "sla_card_sec": 30,
  "min_scores": { "excellent_min": 80, "pass_min": 60 },
  "call": {
    "phone_aon": "+7 (000) 123-45-67",
    "phone_provided": null,
    "phone_onsite": null,
    "foreign_number": false,
    "channel": "МТС",
    "caller_name_known": false,
    "caller_status": null,
    "foreign_language": false,
    "address_auto": { "known": false },
    "sms_thread": [],
    "available_services": ["fire", "ambulance", "police", "gas", "utility", "gormost", "housing", "mosvodokanal", "moscollector", "uprava"]
  },
  "expected": {
    "incident_category": "fire",
    "expected_services": ["fire", "ambulance"],
    "address": { "city": "Москва", "street": "Ленина", "house": "10", "block": null, "flat": "42", "entrance": null, "floor": null, "district": null, "landmarks": "во дворе шлагбаум", "lat": null, "lon": null },
    "victims_count": 2,
    "victims_state": { "consciousness": null, "breathing": null, "trauma": null, "bleeding": null },
    "threat_to_life": true,
    "hazards": ["дым"],
    "caller": { "name": "Петрова Анна", "phone": "+7 (000) 123-45-67", "status": null },
    "incident_time": null,
    "applicant_actions": null,
    "access_for_equipment": null
  },
  "required_fields": ["incident_category", "address.city", "address.street", "address.house", "caller.name", "caller.phone", "description", "victims_count"],
  "timeline": [
    { "seq": 1, "t_sec": 0,   "speaker": "citizen", "emotion": "panic", "tone": "крик",
      "text": "Пожар! Горит квартира, помогите!",
      "expected_actions": ["C1"] },
    { "seq": 2, "t_sec": 4,   "speaker": "citizen", "emotion": "fear", "tone": "взволнованно",
      "text": "Я на улице, а там люди остались! Дым из окон идёт!",
      "expected_actions": ["B3", "C2"] },
    { "seq": 3, "t_sec": 90,  "speaker": "citizen", "emotion": "nervous", "tone": "нервно",
      "text": "Да дымом всё затянуло, соседи на верхних этажах!",
      "expected_actions": ["C5"] }
  ],
  "quick_replies": [
    { "id": "qr-addr", "label": "Уточнить адрес", "text": "Назовите точный адрес: город, улица, дом, квартира." },
    { "id": "qr-srv",  "label": "Какие службы вызвать", "text": "Какие экстренные службы уже вызваны?" }
  ],
  "hints_enabled": true,
  "grammar_check": true
}
```

Поля добавлены по PLAN (Блок 5) и Инструкции: телефоны АОН/предоставленный/на место +
канал + СМС; адрес с домом в единой строке + геометка + ориентиры; подробности
(состояние, угроза, факторы, действия заявителя, доступ, время, координаты);
`expected_services` + ТЭГи; уровни сложности; `sla_*`; пороги; `expected_actions`.

## 6. `rubrics/<rubric_id>.json` — машиночитаемый чек-лист A–F+X

Соответствует `OPERATOR-CHECKLIST.md` и PLAN §7 (группы A–F + критические X;
настроить по `OPERATOR-CHECKLIST` / регламенту МЧС/ЦОВ-112).

```json
{
  "id": "rubric-112-base",
  "title": "Базовый протокол ответа оператора 112",
  "group_weights": { "A": 0.10, "B": 0.20, "C": 0.25, "D": 0.20, "E": 0.10, "F": 0.15 },
  "groups": [
    { "id": "A", "title": "Приём вызова", "items": [
        { "id": "A2", "title": "Приветствие и наименование службы",
          "check": "text", "required": ["112", "слушаю"], "weight": 0.30 },
        { "id": "A1", "title": "Ответ за ≤ 8 секунд",
          "check": "timing", "target_sec": 8, "window_sec": [8, 10], "weight": 0.25 }
    ]}
  ],
  "forbidden": [
    { "id": "X5", "title": "Грубость", "check": "forbidden", "penalty_ratio": 0.5 },
    { "id": "X7", "title": "Небезопасная инструкция", "check": "forbidden", "penalty_ratio": 0.4 }
  ],
  "category_subsets": {
    "fire":    ["D1","D2","D3","D4","D5","D6"],
    "medical": ["D1","D2","D3","D4","D5"],
    "gas":     ["D1","D2","D3","D4","D5"],
    "dtp":     ["D1","D2","D3","D4"],
    "urban":   ["D-common"]
  },
  "critical": ["X1","X2","X3","X4","X6"]
}
```

Правила: `score_group = Σ(выполнен×вес)×100`; `total = Σ(group×weight_group)`;
≥ 80 отлично, 60–79 зачтено, < 60 или любая X-критика (X1–X4, X6) → не зачтено;
X5 −50%, X7 −40%. Полный перечень — в `OPERATOR-CHECKLIST.md` §2–8.

## 7. `results/<session_id>.json` — результат тренировки (пишет бэкенд)

```json
{
  "session_id": "s-2026-001",
  "user_id": "u-001",
  "scenario_id": "scn-001",
  "rubric_id": "rubric-112-base",
  "started_at": "2026-09-18T10:00:00Z",
  "finished_at": "2026-09-18T10:03:42Z",
  "answer_latency_sec": 5.4,
  "card_duration_sec": 28,
  "sla_answer_sec": 8,
  "sla_card_sec": 30,
  "messages": [
    { "ts": "10:00:00.000", "sender": "citizen", "text": "Пожар! Горит квартира..." },
    { "ts": "10:00:05.200", "sender": "operator", "text": "Единая служба спасения, диспетчер Иванов, слушаю вас." }
  ],
  "form": {
    "incident_category": "fire",
    "address": { "city": "Москва", "street": "Ленина", "house": "10", "flat": null },
    "caller_name": "Петрова", "phone": "+7...", "victims": 2
  },
  "dispatched_services": ["fire"],
  "scores": { "A": 1.0, "B": 0.66, "C": 0.85, "D": 0.9, "E": 1.0, "F": 0.7 },
  "total_score": 82.4,
  "verdict": "excellent",
  "failed_items": [ { "id": "B3", "reason": "не указана квартира", "dialog_ts": "10:01:12.000" } ],
  "critical_failures": [],
  "grammar": { "errors": 1, "notes": "падеж адреса" },
  "expert": { "score": null, "comment": null, "by": null, "audit": [] },
  "detail": {}
}
```

Добавлены по PLAN §7–8: длительности и SLA (`answer_latency_sec` vs 8, `card_duration_sec`
vs 30), привязка `failed_items` к моменту диалога, грамматика ручного ввода vs эталон,
экспертная оценка поверх автооценки (с аудитом правок). Экспорт результата — CSV/PDF/JSON.

## 8. Правила интеграции

- Время — ISO 8601 UTC (со стартом сессии из `scenario.started`), таймеры фронта — производные значения (`sla_answer_sec` 8–10, `sla_card_sec` 30; превышение — красная подсветка).
- Оценка (расчёт `scores`, `verdict`, `failed_items`) выполняется бэкендом; фронт только отображает. Проверки: сравнение ручного ввода с эталоном, контроль тайминга/порядка (передача до завершения), запрещённые фразы, грамматика; экспертная оценка преподавателя поверх автооценки (с аудитом правок).
- Черновая оценка на фронте допустима для мгновенной обратной связи `ChecklistProgress`, при сохранении заменяется расчётом бэкенда.
- Незнакомые ключи в JSON не ломают фронт (расширяемость), неизвестные `check`-типы в рубрике пропускаются с предупреждением.
- Контур изолированный, внешних интеграций нет; внутренний API — только для собственных модулей; импорт пакетных обновлений учебных материалов — вручную; экспорт CSV (статистика), PDF (документы/сертификаты), JSON (обмен), время формирования ≤ 30 сек.
- Аудит всех действий; бэкап ≥ 1 раза в сутки; журналы безопасности ≥ 6 мес.
- Типы проверки рубрики: `text` / `key_extract` / `option` / `timing` / `order` / `forbidden` (см. `OPERATOR-CHECKLIST.md` §1).