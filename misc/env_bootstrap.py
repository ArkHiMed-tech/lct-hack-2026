"""Авто-создание .env из коробки.

Новый клиент клонирует репозиторий, в котором .env отсутствует (он в gitignore).
Чтобы ``python run.py`` / ``uvicorn main:app`` работали сразу, при старте
создаём .env из значений по умолчанию, если файла нет.
"""
from __future__ import annotations

from pathlib import Path

DEFAULT_ENV = """\
# Создан автоматически при первом запуске (см. misc/env_bootstrap.py).
# Подставьте реальные ключи при необходимости.
APP_ENV=prod
# Ключ Яндекс.Геокодера для /api/map_valid (без него маршрут вернёт 503).
YANDEX_GEOCODER_API_KEY=
# Необязательно: фиксированный ключ шифрования ПДн в БД (Fernet-ключ).
# Если пусто — будет создан локальный файл .dbkey (тоже в gitignore).
DB_ENCRYPTION_KEY=
# Отключает загрузку тяжёлой STT-модели (1 — stub-режим, старт за секунды).
ASR_DISABLED=1
HOST=127.0.0.1
PORT=8000
"""


def ensure_env_file(env_path: str | Path) -> Path:
    """Создать .env со значениями по умолчанию, если его нет. Возвращает путь."""
    path = Path(env_path)
    if not path.exists():
        path.write_text(DEFAULT_ENV, encoding="utf-8")
        print(f".env не найден — создан {path} со значениями по умолчанию.")
    return path
