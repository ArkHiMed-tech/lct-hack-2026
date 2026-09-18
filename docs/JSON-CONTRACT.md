# Предлагаемый JSON-формат обмена с бэкендом (FastAPI)

Черновик контракта данных между фронтендом и бэкендом. Бэкенд отдаёт фронту файлы по фиксированным путям (либо REST-эндпоинтами, отдающими те же структуры). Файлы — предложение для обсуждения, аналог схемы на этапе прототипа.

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
  "schema_version": 1,
  "scenarios_path": "scenarios/catalog.json",
  "users_path": "users.json",
  "results_path": "results",
  "rubrics_path": "rubrics",
  "sla_answer_sec": 8,
  "score_group_weights": { "A": 0.10, "B": 0.20, "C": 0.25, "D": 0.20, "E": 0.10, "F": 0.15 },
  "verdicts": { "excellent_min": 80, "pass_min": 60 }
}
```

## 2. `roles.json`, `users.json`

```json
// roles.json
[ { "id": "student", "title": "Обучающийся" },
  { "id": "teacher", "title": "Преподаватель" },
  { "id": "admin",  "title": "Администратор" } ]
```

```json
// users.json
[ { "id": "u-001", "name": "Иванов Иван Иванович", "role": "student",
    "group": "Группа-1", "last_name": "Иванов", "active": true } ]
```

## 3. `services.json` (справочник экстренных служб)

```json
[ { "id": "fire",       "title": "Пожарно-спасательная",    "phone": "101", "code": "01" },
  { "id": "ambulance",  "title": "Скорая медицинская",      "phone": "103", "code": "03" },
  { "id": "police",     "title": "Полиция",                 "phone": "102", "code": "02" },
  { "id": "gas",        "title": "Аварийная газовая",       "phone": "104", "code": "04" },
  { "id": "utility",    "title": "Аварийная городская",     "phone": "105", "code": "05" } ]
```

## 4. `scenarios/catalog.json`

```json
[ { "id": "scn-001", "title": "Пожар в многоквартирном доме", "category": "fire",
    "difficulty": "medium", "severity": "high", "rubric_id": "rubric-112-base",
    "done": true, "best_score": 82, "estimate_sec": 240 } ]
```

## 5. `scenarios/<scenario_id>.json`

```json
{
  "id": "scn-001",
  "title": "Пожар в многоквартирном доме",
  "category": "fire",
  "difficulty": "medium",
  "severity": "high",
  "rubric_id": "rubric-112-base",
  "sla_answer_sec": 8,
  "min_scores": { "excellent_min": 80, "pass_min": 60 },
  "call": {
    "phone": "+7 (000) 123-45-67",
    "caller_name_known": false,
    "address_auto": { "known": false },
    "available_services": ["fire", "ambulance", "police", "gas"]
  },
  "expected": {
    "incident_category": "fire",
    "expected_services": ["fire", "ambulance"],
    "address": { "city": "Воронеж", "street": "Ленина", "house": "10", "flat": "42" },
    "victims_count": 2,
    "caller": { "name": "Петрова Анна" }
  },
  "timeline": [
    { "seq": 1, "t_sec": 0,   "speaker": "citizen", "emotion": "panic",
      "text": "Пожар! Горит квартира, помогите!" },
    { "seq": 2, "t_sec": 4,   "speaker": "citizen", "emotion": "fear",
      "text": "Я на улице, а там люди остались! Дым из окон идёт!" },
    { "seq": 3, "t_sec": 90,  "speaker": "citizen", "emotion": "nervous",
      "text": "Да дымом всё затянуло, соседи на верхних этажах!" }
  ],
  "quick_replies": [
    { "id": "qr-addr", "label": "Уточнить адрес", "text": "Назовите точный адрес: город, улица, дом, квартира." },
    { "id": "qr-srv",  "label": "Какие службы вызвать", "text": "Какие экстренные службы уже вызваны?" }
  ],
  "hints_enabled": true
}
```

## 6. `rubrics/<rubric_id>.json` — машиночитаемый чек-лист

Соответствует `OPERATOR-CHECKLIST.md` (группы A–F + критические X).

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
          "check": "timing", "target_sec": 8, "weight": 0.25 }
    ]}
  ],
  "forbidden": [
    { "id": "X5", "title": "Грубость", "check": "forbidden", "penalty_ratio": 0.5 }
  ],
  "category_subsets": {
    "fire":    ["D1","D2","D3","D4","D5","D6"],
    "medical": ["D1","D2","D3","D4","D5"],
    "gas":     ["D1","D2","D3","D4","D5"],
    "dth":     ["D1","D2","D3","D4"]
  },
  "critical": ["X1","X2","X3","X4","X6"]
}
```

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
  "messages": [
    { "ts": "10:00:00.000", "sender": "citizen", "text": "Пожар! Горит квартира..." },
    { "ts": "10:00:05.200", "sender": "operator", "text": "Единая служба спасения, диспетчер Иванов, слушаю вас." }
  ],
  "form": {
    "incident_category": "fire",
    "address": { "city": "Воронеж", "street": "Ленина", "house": "10", "flat": null },
    "caller_name": "Петрова", "phone": "+7...", "victims": 2
  },
  "dispatched_services": ["fire"],
  "scores": { "A": 1.0, "B": 0.66, "C": 0.85, "D": 0.9, "E": 1.0, "F": 0.7 },
  "total_score": 82.4,
  "verdict": "excellent",
  "failed_items": [ { "id": "B3", "reason": "не указана квартира" } ],
  "critical_failures": []
}
```

## 8. Правила интеграции (предложение)

- Время — ISO 8601 UTC (со стартом сессии из `scenario.started`), таймеры фронта — производные значения.
- Оценка (расчёт `scores`, `verdict`, `failed_items`) выполняется бэкендом; фронт только отображает.
- Черновая оценка на фронте допустима для мгновенной обратной связи `ChecklistProgress`, при сохранении заменяется расчётом бэкенда.
- Незнакомые ключи в JSON не ломают фронт (расширяемость), неизвестные `check`-типы в рубрике пропускаются с предупреждением.