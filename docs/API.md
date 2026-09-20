# API бэкенда — описание всех ручек

Базовый URL: `http://127.0.0.1:8000` (фронт ходит через vite-proxy `/api` → бэкенд).
Формат: JSON. Время — ISO 8601 UTC.

Решения (зафиксированы):
- Авторизация — **простой login/password без токенов**: `POST /api/auth/login`
  возвращает пользователя, фронт хранит его в `localStorage`.
- Фронт **полностью переходит на API**, fallback на `public/data/*.json` нет.
  Статика переезжает в БД через сид при старте.

Статусы ручек: ✅ есть в `main.py` · ❌ требуется · 🔧 есть, но требует правок.

---

## 1. Служебные

### `GET /api/health` ✅
Проверка состояния.

Ответ:
```json
{ "status": "ok", "frontend_build_exists": true, "database_exists": true }
```

---

## 2. Авторизация

### `POST /api/auth/login` ❌
Проверка логина/пароля по таблице `users`.

Запрос:
```json
{ "login": "umc_operdds1", "password": "dds112-1" }
```

Успех (200) — пользователь **без пароля**:
```json
{
  "id": "u-001",
  "login": "umc_operdds1",
  "name": "Иванова Мария Петровна",
  "last_name": "Иванова",
  "role": "student",
  "post": "Оператор ДДС",
  "group": "Группа 1",
  "active": true
}
```

Ошибка (401):
```json
{ "detail": "Неверный логин или пароль" }
```

Неактивный пользователь (403):
```json
{ "detail": "Пользователь деактивирован" }
```

Сид пользователей (роли `student` / `teacher` / `admin` уже есть в таблице `roles`):

| login | password | id | name | role | post |
|---|---|---|---|---|---|
| `umc_operdds1` | `dds112-1` | `u-001` | Иванова Мария Петровна | student | Оператор ДДС |
| `umc_operdds2` | `dds112-2` | `u-002` | Смирнов Алексей Сергеевич | student | Оператор ДДС |
| `umc_teacher` | `teach112` | `u-003` | Кузнецов Никита Андреевич | teacher | Преподаватель |
| `umc_admin` | `admin112` | `u-004` | Соколова Дарья Викторовна | admin | Администратор |

Разделение на фронте: оператор (`student`) видит в Журнале только свои
тренировки, преподаватель/админ — все; `/admin` закрыт только для `admin`.

---

## 3. Пользователи и роли

### `POST /api/users/create` ✅
Создание/перезапись пользователя. Тело — `User`
(`login`, `password`, `email`, `name`, `last_name`, `role`, `group_name`, `active`).

### `GET /api/users` ❌
Справочник для Журнала (имена).
```json
[ { "id": "u-001", "name": "Иванова Мария Петровна" } ]
```

### `PUT /api/users/{id}` ❌ (P2, админка)
Обновление пользователя (роль, группа, активность).

### `GET /api/roles` ❌ (P2, админка)
```json
[ { "id": "student", "title": "Обучающийся" } ]
```

---

## 4. Сценарии

### `GET /api/scenarios` ❌
Каталог для Главной, Списка происшествий, Журнала.
```json
[
  {
    "id": "scn-001",
    "title": "Пожар в многоквартирном доме",
    "category": "fire",
    "difficulty": "medium",
    "severity": "high",
    "estimate_sec": 240,
    "status": "done",
    "best_score": 82,
    "summary": "Жалоба на сильное задымление…"
  }
]
```

### `GET /api/scenarios/{id}` ❌
Полный сценарий для Симулятора: `id`, `title`, `category`, `difficulty`,
`severity`, `rubric_id`, `sla_answer_sec`, `call` (`phone`,
`caller_name_known`, `address_auto`, `available_services`),
`expected` (`incident_category`, `expected_services`, `address`, `victims_count`,
…), `required_fields`, `timeline` (`seq`, `t_sec`, `speaker`, `emotion`,
`text`), `quick_replies` (`label`, `text`). Структура — по `docs/JSON-CONTRACT.md §5`.

### `POST /api/scenarios`, `PUT /api/scenarios/{id}` ❌ (P2, админка)
Конструктор сценариев. Таблица `scenarios` уже есть, нужны поля как в §5
(сейчас в таблице только часть колонок).

---

## 5. Рубрики

### `GET /api/rubrics/{id}` ❌
Рубрика для живого чек-листа и оценки, структура — по контракту §6:
`id`, `title`, `group_weights`, `groups` (`id`, `title`, `items` с `check`,
`weight`, …), `category_subsets`, `critical`.

### `PUT /api/rubrics/{id}` ❌ (P2, админка)
Редактирование чек-листов A–F и критических ошибок.

---

## 6. Тренировки: оценка и результаты

### `POST /api/sessions/finish` ❌
Главная ручка Симулятора. Принимает итог тренировки, **авторитетно считает
оценку на бэкенде** (контракт §8), сохраняет результат, возвращает его.

Запрос:
```json
{
  "user_id": "u-001",
  "scenario_id": "scn-001",
  "answer_latency_sec": 5.4,
  "messages": [ { "sender": "citizen", "text": "…" } ],
  "form": { "what": "…", "incident_category": "fire", "address": "…" },
  "services": ["fire", "ambulance"],
  "dispatched_at_ms": 1726650000000,
  "ended_at_ms": 1726650200000
}
```

Ответ — объект результата (контракт §7): `session_id`, `scenario_id`,
`rubric_id`, `groups_meta`, `answer_latency_sec`, `messages`, `form`,
`dispatched_services`, `scores`, `total_score`, `verdict`
(`excellent`/`pass`/`fail`), `failed_items` (`id`, `group`, `title`),
`critical_failures`, `detail`.

### `GET /api/results?user_id=...` ❌
Список результатов для Главной (статистика), Списка (средний балл) и Журнала.
Без `user_id` — все (преподаватель/админ), с `user_id` — свои (оператор).
```json
[
  {
    "session_id": "s-2026-001",
    "user_id": "u-001",
    "scenario_id": "scn-001",
    "score": 82.4,
    "verdict": "excellent",
    "date": "2026-09-18T10:03:42Z"
  }
]
```

Поля `session_id`, `score`, `date`, `verdict` обязательны — их читает Журнал.

---

## 7. Карточки происшествий и диалог (P1)

### `POST /api/reports/create` ✅
Есть. Сохраняет `incident_reports` + `dispatched_services`, возвращает
`{message, report_id, services}`.

### `POST /api/reports/{id}/messages` ❌
Сохранение реплик диалога в `app_messages` (`report_id`, `sender`, `text`).
Сейчас диалог не сохраняется никуда.

### `GET /api/reports?user_id=...` ❌
Список сохранённых карточек.

### `GET /api/reports/{id}` ❌
Карточка с полями, службами и диалогом.

---

## 8. Карта «страница фронта → ручки»

| Страница | Ручки |
|---|---|
| Вход (`/login`) | `POST /api/auth/login` |
| Главная (`/`) | `GET /api/results?user_id=`, `GET /api/scenarios` |
| Список происшествий (`/incidents`) | `GET /api/scenarios`, `GET /api/results?user_id=` |
| Карточка/симулятор (`/scenario/:id`) | `GET /api/scenarios/{id}`, `GET /api/rubrics/{id}`, `POST /api/sessions/finish`, (`POST /api/reports/create`, `POST /api/reports/{id}/messages`) |
| Результаты (`/results`) | данные из `POST /api/sessions/finish` |
| Журнал (`/journal`) | `GET /api/results`, `GET /api/users`, `GET /api/scenarios` |
| Админка (`/admin`) | P2-ручки раздела 3–5 |

## 9. Известные проблемы `main.py`

1. `app.on_event("startup")` на строке 127 стоит без декоратора —
   `initialize_database()` не вызывается, таблицы/роли не создаются.
2. В таблице `results` нет колонок под `scores`/`messages`/`form`/`verdict`-детали —
   понадобится расширение схемы или отдельная таблица/JSON-поле для объекта результата §7.
3. В таблице `scenarios` нет полей `timeline`, `quick_replies`, `expected`,
   `required_fields` — нужны для `GET /api/scenarios/{id}` (JSON-колонки).
4. Нет таблицы `rubrics` — нужна для раздела 5.
5. Пароли в `users` хранятся открытым текстом — для учебного стенда допустимо,
   но фиксируем как известное ограничение.
