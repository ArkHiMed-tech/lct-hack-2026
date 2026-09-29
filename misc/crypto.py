"""Шифрование данных в БД (at rest).

Схема: клиент (браузер) -> API -> [кодирование] -> БД -> [декодирование] -> API -> клиент.
Контракт API не меняется: шифрование/расшифровка только на границе backend<->SQLite.

- Контентные текстовые колонки и JSON-blob'ы: Fernet (AES-128-CBC + HMAC),
  envelope-префикс ``enc1:`` (сырые значения без префикса читаются как есть —
  обратная совместимость и идемпотентная миграция).
- ``login``: ХРАНИТСЯ ОТКРЫТЫМ ТЕКСТОМ (нормализованный: strip + lower) —
  точный поиск ``WHERE login = ?`` и cookie-сессия работают без ключей.
  Старый HMAC-индекс ``hmac1:`` больше не создаётся; чтение таких строк
  поддерживается только миграцией (см. ``is_login_index``).
- ``password``: односторонний хэш PBKDF2-HMAC-SHA256 (``pbkdf2:``).
  Проверка — ``password_matches`` (понимает и legacy ``enc1:``/plaintext
  для плавной миграции со старых БД).
- Структурные поля (int-PK, FK-id вида ``u-001``/``card-5``, timestamps,
  числовые скоринги, флаги) — открытый текст: это не ПДн, нужно для
  связей/сортировок.

Ключ: env ``DB_ENCRYPTION_KEY`` (Fernet-ключ, ``Fernet.generate_key()``);
для dev — автогенерация локального файла ``.dbkey`` (0600, в gitignore).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

BASE_DIR = Path(__file__).resolve().parents[1]
KEY_ENV = "DB_ENCRYPTION_KEY"
DEV_KEY_FILE = BASE_DIR / ".dbkey"

ENC_PREFIX = "enc1:"
HMAC_PREFIX = "hmac1:"

_fernet: Fernet | None = None
_hmac_key: bytes | None = None


def _load_fernet_key() -> bytes:
    """Fernet-ключ (base64): из env, из dev-файла или свежесгенерированный."""
    raw = os.getenv(KEY_ENV, "").strip()
    if raw:
        try:
            Fernet(raw.encode("ascii"))
            return raw.encode("ascii")
        except Exception as exc:
            raise ValueError(
                f"{KEY_ENV} должен быть Fernet-ключом (Fernet.generate_key())"
            ) from exc
    if DEV_KEY_FILE.exists():
        stored = DEV_KEY_FILE.read_text(encoding="utf-8").strip()
        Fernet(stored.encode("ascii"))  # валидация
        return stored.encode("ascii")
    fernet_key = Fernet.generate_key()
    DEV_KEY_FILE.write_text(fernet_key.decode("ascii"), encoding="utf-8")
    try:
        os.chmod(DEV_KEY_FILE, 0o600)
    except OSError:
        pass
    return fernet_key


def _keys() -> tuple[Fernet, bytes]:
    global _fernet, _hmac_key
    if _fernet is None or _hmac_key is None:
        fernet_key = _load_fernet_key()
        _fernet = Fernet(fernet_key)
        master = base64.urlsafe_b64decode(fernet_key)
        _hmac_key = hashlib.sha256(master + b"|search").digest()
    return _fernet, _hmac_key


def reset_keys() -> None:
    """Сброс кэша ключей (для тестов со сменой env)."""
    global _fernet, _hmac_key
    _fernet, _hmac_key = None, None


def is_encrypted(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def enc_text(value: Any) -> Any:
    """Шифрование текстовой колонки. None/'' сохраняются как есть."""
    if value is None or value == "":
        return value
    text = value if isinstance(value, str) else str(value)
    if text.startswith(ENC_PREFIX):
        return text
    fernet, _ = _keys()
    return ENC_PREFIX + fernet.encrypt(text.encode("utf-8")).decode("ascii")


def dec_text(value: Any) -> Any:
    """Расшифровка; значения без префикса возвращаются как есть."""
    if value is None or value == "":
        return value
    if isinstance(value, str) and value.startswith(ENC_PREFIX):
        fernet, _ = _keys()
        try:
            return fernet.decrypt(value[len(ENC_PREFIX):].encode("ascii")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("DB value failed authentication (wrong key?)") from exc
    return value


def enc_blob(payload: Any) -> str:
    """Шифрование JSON-blob'а целиком. Пустые значения -> ''."""
    if payload is None or payload == "":
        return ""
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    return enc_text(text)


def dec_blob(value: Any) -> Any:
    """Расшифровка blob'а в исходный объект (dict/list/str)."""
    if value is None or value == "":
        return {} if value is None else value
    return json.loads(dec_text(value))


def login_index(login: str) -> str:
    """DEPRECATED: раньше логин хранился HMAC-индексом, теперь — plaintext.

    Оставлена для чтения/миграции старых БД. Новый код должен использовать
    :func:`normalize_login`.
    """
    _, hmac_key = _keys()
    digest = hmac.new(hmac_key, str(login).encode("utf-8"), hashlib.sha256).hexdigest()
    return HMAC_PREFIX + digest


def is_login_index(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(HMAC_PREFIX)


def normalize_login(login: Any) -> str:
    """Канонический вид логина: plaintext, без пробелов, в нижнем регистре."""
    return str(login or "").strip().lower()


# --- Пароли: односторонний хэш (PBKDF2, только stdlib) ---

PWD_PREFIX = "pbkdf2:"
_PWD_ITERATIONS = 210_000


def hash_password(password: str) -> str:
    """Хэш пароля для хранения. Идемпотентен: хэш повторно не хэшируется."""
    if is_password_hash(password):
        return password
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", str(password or "").encode("utf-8"), salt.encode("ascii"), _PWD_ITERATIONS
    ).hex()
    return f"{PWD_PREFIX}{_PWD_ITERATIONS}${salt}${digest}"


def is_password_hash(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(PWD_PREFIX)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, rest = str(stored_hash).split(PWD_PREFIX, 1)
        iterations_str, salt, digest = rest.split("$", 2)
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            str(password or "").encode("utf-8"),
            salt.encode("ascii"),
            int(iterations_str),
        ).hex()
        return hmac.compare_digest(expected, digest)
    except (ValueError, AttributeError):
        return False


def password_matches(password: str, stored: Any) -> bool:
    """Проверка пароля против любого legacy-формата.

    - ``pbkdf2:...`` — штатная проверка хэша;
    - ``enc1:...`` — расшифровка Fernet и сравнение (миграция со старых БД);
    - иначе — прямое сравнение с plaintext (самые старые БД).
    """
    if stored is None:
        return False
    if is_password_hash(stored):
        return verify_password(password, stored)
    if isinstance(stored, str) and stored.startswith(ENC_PREFIX):
        try:
            return dec_text(stored) == password
        except ValueError:
            # Чужой ключ (БД с другой машины) — расшифровать нельзя.
            return False
    return stored == password
