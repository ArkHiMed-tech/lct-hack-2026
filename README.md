# Диспетчер 112 — учебный симулятор операторов экстренных служб

Тренажёр подготовки диспетчеров Системы-112 для хакатона **ЛЦТ 2026**.
Студент принимает учебный звонок в реальном времени: слушает абонента (TTS),
отвечает голосом или текстом (STT), заполняет карточку происшествия по
классификатору, выбирает службы реагирования — и получает автоматическую оценку
по рубрике A–F с разбором ошибок.

Backend — **FastAPI + SQLite**, frontend — **React + Vite**, голос — **faster-whisper (STT)**
и **Piper (TTS)**, адреса — **Яндекс.Геокодер**.

---

## Возможности

- **Симулятор звонка** — таймлайн реплик абонента, таймер с SLA ответа (≤ 8 сек),
  быстрые ответы-подсказки, пауза/завершение, живой прогресс чек-листа.
- **Карточка 112** — форма происшествия (что / где / когда / кто / пострадавшие /
  угрозы / факторы), адрес с валидацией через Яндекс.Карты, округ Москвы.
- **Классификатор происшествий** — дерево из xlsx-классификатора МВД+Департамент:
  Раздел → Место → Что → Проявление → лист (Номер + Итоговый тип), поиск,
  breadcrumb, расчёт привлекаемых/информируемых служб и ВИС-класса по флагам.
- **Голосовой режим** — WebSocket `/api/connection`: стриминг аудио, распознавание
  (faster-whisper, stub без модели), озвучка реплик сценария и оператора.
- **Оценка** — авторитетный скоринг на бэкенде по рубрике (`group_weights`,
  `critical`), вердикты `excellent / pass / fail`, разбор `failed_items`.
- **Роли и журнал** — `student` видит только свои тренировки, `teacher`/`admin` — все;
  `/admin` только для администратора. Журнал, статистика, средний балл.
- **Безопасность ПДн** — шифрование полей БД at rest (Fernet), хэши паролей PBKDF2,
  самовосстановление сид-пользователей при клоне чужой БД.
- **Работа из коробки** — `python run.py` сам ставит зависимости, создаёт `.env`,
  инициализирует БД с сидами, собирает фронт и поднимает всё на одном порту.

## Демо-доступ (сиды из коробки)

| Логин | Пароль | Роль | ФИО |
|---|---|---|---|
| `umc_operdds1` | `dds112-1` | student (Оператор ДДС) | Иванова Мария Петровна |
| `umc_operdds2` | `dds112-2` | student (Оператор ДДС) | Смирнов Алексей Сергеевич |
| `umc_teacher` | `teach112` | teacher (Преподаватель) | Кузнецов Никита Андреевич |
| `umc_admin` | `admin112` | admin (Администратор) | Соколова Дарья Викторовна |

## Архитектура

```
┌─────────────┐      HTTP / WS       ┌──────────────┐
│ React + Vite│ ◄──────────────────► │ FastAPI      │
│  (SPA /dist)│  /api/*, /assets, /* │ main.py      │
└─────────────┘                      └──────┬───────┘
                                            │
        ┌───────────┬───────────┬───────────┼────────────┐
        ▼           ▼           ▼           ▼            ▼
   routers/    misc/       asr/ (STT)  TTS-сервис  SQLite db.db
   auth, users, incident_tree_api, faster-    Piper/      (Fernet +
   scenarios,   card_graph, whisper,   stub      PBKDF2)
   rubrics,     card_generator recording
   sessions,
   classifier,
   connection,
   results,
   reports
```

Бэкенд отдаёт и API, и собранный фронт (SPA-fallback на `index.html`),
поэтому в проде достаточно одного процесса на `HOST:PORT`.

## Технологии

- **Backend:** Python 3.10+, FastAPI, Uvicorn, Pydantic, httpx, cryptography
- **Frontend:** React 18, React Router 7, Vite 7
- **Голос:** faster-whisper + numpy (STT, опционально), piper-tts (TTS, опционально)
- **Карты:** Yandex Geocoder API v1 (reverse для дом/улица, direct для вода/лес)
- **Хранилище:** SQLite (`db.db`), сиды сценариев/рубрик из `frontend/public/data/`

## Структура репозитория

```
lct-hack-2026/
├── main.py               # FastAPI app, /api/health, /api/map_valid, раздача SPA
├── run.py                # точка входа: зависимости → .env → фронт → uvicorn
├── database.py           # схема SQLite, сиды, миграции шифрования
├── models.py             # Pydantic-модели (User, IncidentReport)
├── routers/              # auth, users, roles, scenarios, rubrics, sessions,
│                         # connection (WS), results, reports, classifier
├── misc/                 # incident_tree_api, card_graph, card_generator,
│                         # crypto, tts_service, env_bootstrap, rag_responses
├── asr/                  # asr_service (whisper/stub), recording
├── tts-agent/            # отдельный TTS-микросервис (docker-compose)
├── frontend/             # React SPA (src/pages, src/components, public/data)
│   └── public/data/      # scenarios/catalog.json + scn-*.json, rubrics/*.json
├── docs/                 # API.md, JSON-CONTRACT.md, UI-SPEC.md, OPERATOR-CHECKLIST.md
├── tests/                # pytest: routes, classifier, card_generator, crypto
├── requirements.txt      # минимум для старта
└── requirements-stt.txt  # тяжёлые STT/TTS зависимости (опционально)
```

## Быстрый старт

Требуется: **Python 3.10+**, для фронта — **Node.js 18+** (опционально, соберётся сам при наличии npm).

```bash
cd lct-hack-2026

# Прод (фронт соберётся автоматически, всё на одном порту)
python run.py

# Дев (hot-reload бэка, без сборки фронта)
python run.py dev

# Только фронт в dev-режиме (прокси /api → 127.0.0.1:8000)
cd frontend && npm install && npm run dev
```

Откройте `http://127.0.0.1:8000` (прод) или `http://localhost:5173` (фронт-dev).
Проверка: `GET /api/health` → `{"status":"ok", ...}`.

Флаги `run.py`:

| Аргумент | Эффект |
|---|---|
| `dev` | `APP_ENV=dev`, reload, фронт не собирается |
| `--rebuild` | принудительная пересборка `frontend/dist` в проде |

## Конфигурация (.env)

`.env` создаётся автоматически из `.env.example` при первом старте.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `APP_ENV` | `prod` | `prod` — сид из БД, `dev` — пересев сценариев/рубрик из JSON |
| `HOST` / `PORT` | `127.0.0.1` / `8000` | адрес сервера |
| `YANDEX_GEOCODER_API_KEY` | — | ключ Геокодера для `/api/map_valid` (алиас `YANDEX_MAPS_API_KEY`) |
| `DB_ENCRYPTION_KEY` | — | Fernet-ключ ПДн; если пуст — локальный `.dbkey` |
| `ASR_DISABLED` | `1` | `1` — stub-STT (старт за секунды), `0` — грузить whisper |

Без ключа Яндекса `/api/map_valid?type=house` вернёт `503` — остальное работает.

## API (кратко)

Полное описание — в [`docs/API.md`](docs/API.md), контракт данных — в
[`docs/JSON-CONTRACT.md`](docs/JSON-CONTRACT.md).

| Метод | Путь | Назначение |
|---|---|---|
| `GET` | `/api/health` | статус, наличие фронта и БД |
| `GET` | `/api/map_valid?type=house\|street\|water\|forest` | адрес (дом/улица) или координаты (вода/лес) Москвы |
| `POST` | `/api/auth/login` | `{login, password}` → пользователь без пароля |
| `GET/POST/PUT` | `/api/users`, `/api/users/create`, `/api/users/{id}` | справочник и CRUD пользователей |
| `GET` | `/api/roles` | `student / teacher / admin` |
| `GET` | `/api/scenarios`, `/api/scenarios/{id}` | каталог и полный сценарий (таймлайн, expected) |
| `GET/PUT` | `/api/rubrics/{id}` | чек-лист A–F + critical |
| `POST` | `/api/sessions/finish` | приём итога тренировки, скоринг, сохранение |
| `WS` | `/api/connection` | голосовой диалог (аудио ↔ текст, TTS) |
| `GET` | `/api/results?user_id=` | результаты (свои / все) |
| `POST/GET` | `/api/reports/create`, `/api/reports…` | карточки происшествий и сообщения диалога |
| `GET` | `/api/classifier/sections\|leaves\|search\|leaf/{code}\|tree\|children\|breadcrumb/{code}\|dispatch\|vis-class` | дерево классификатора и службы |

Авторизация учебная: без токенов, пользователь хранится в `localStorage`.

Оценка: `total_score = Σ group_score × group_weight` со штрафами `forbidden`
и автопровалом по `critical`; пороги `excellent ≥ 80`, `pass ≥ 60`
(переопределяются в сценарии/рубрике).

## Frontend-страницы

| Путь | Страница |
|---|---|
| `/login` | вход по сид-парам выше |
| `/` | дашборд: сценарии, статистика, «Старт» |
| `/scenario/:id` | рабочее место диспетчера (симулятор) |
| `/card` | карточка 112 (форма + классификатор + службы) |
| `/results` | итог тренировки: балл, группы, пропуски, диалог |
| `/journal` | журнал тренировок с фильтрами |
| `/admin` | пользователи, сценарии, рубрики (только `admin`) |

UI-компоненты и поток описаны в [`docs/UI-SPEC.md`](docs/UI-SPEC.md),
чек-лист оператора — в [`docs/OPERATOR-CHECKLIST.md`](docs/OPERATOR-CHECKLIST.md).

## Голос (STT/TTS)

- По умолчанию `ASR_DISABLED=1`: сервер стартует за секунды, распознавание — stub.
- Полный режим: `pip install -r requirements-stt.txt` и `ASR_DISABLED=0`
  (загрузится faster-whisper; нужен микрофон и модель).
- TTS — Piper через `misc/tts_service.py`; стенд-альтернатива — `tts-agent/`
  (`docker-compose up`).

## База данных и безопасность

- Таблицы: `users`, `roles`, `scenarios`, `rubrics`, `incident_reports`,
  `dispatched_services`, `app_messages`, `results`.
- ПДн (имя, email, тексты сценариев/рубрик) шифруются Fernet at rest,
  логины — открытым текстом (индекс), пароли — только хэш PBKDF2.
- При старте: создание схемы → миграция legacy-шифра → ремонт hmac-логинов →
  восстановление 4 сидов → досев каталога из JSON, если таблицы пустые.
- Чужой `db.db` без своего `.dbkey` не роняет старт: нечитаемые данные
  пересоздаются, сиды восстанавливаются.

## Тесты

```bash
pip install -r requirements.txt
python -m pytest -q
```

Покрыто: health/auth/routes, `map_valid` (адреса/координаты/ошибки Яндекса),
классификатор (sections/search/dispatch/tree), генератор карточек, crypto,
`finish` с DB-рубрикой, WebSocket с реальным TTS-чанком.

## Документация

- [`docs/API.md`](docs/API.md) — все ручки и коды ошибок
- [`docs/JSON-CONTRACT.md`](docs/JSON-CONTRACT.md) — схемы scenario / rubric / result
- [`docs/UI-SPEC.md`](docs/UI-SPEC.md) — страницы и компоненты (G/C/R/A-серии)
- [`docs/OPERATOR-CHECKLIST.md`](docs/OPERATOR-CHECKLIST.md) — эталон действий оператора
- ТЗ и классификатор — в корне (`тз/`, `Классификатор_происшествий_*.xlsx`)

## Ограничения и roadmap

- Авторизация без токенов/JWT — только для учебного стенда.
- Фронт в проде — статика `frontend/dist`, собранная Vite.
- Дальше: JWT + refresh, конструктор сценариев/рубрик в админке, экспорт журнала,
  геопортал на карте, потоковый partial-STT, метрики типичных ошибок группы.
