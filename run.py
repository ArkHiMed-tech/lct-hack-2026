import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Автодоставка зависимостей при запуске (до импорта uvicorn,
# чтобы скрипт не падал на чистой машине).
REQUIRED_PACKAGES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "cryptography": "cryptography",
    "dotenv": "python-dotenv",
}


def ensure_dependencies() -> None:
    missing = [
        pkg for pkg, module in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(module) is None
    ]
    if not missing:
        return
    requirements = BASE_DIR / "requirements.txt"
    if requirements.exists():
        # Ставим всё из requirements.txt — там зафиксирован минимум для старта.
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements)],
            check=True,
        )
    else:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *missing],
            check=True,
        )


ensure_dependencies()

import uvicorn  # noqa: E402

from misc.env_bootstrap import ensure_env_file  # noqa: E402


def _load_env_file() -> None:
    """Подхватить .env (создав из коробки), чтобы HOST/PORT/ключи применились."""
    ensure_env_file(BASE_DIR / ".env")
    try:
        from dotenv import load_dotenv

        load_dotenv(BASE_DIR / ".env")
    except ImportError:
        # Крайний случай: dotenv не встал — разберём KEY=VALUE вручную.
        for line in (BASE_DIR / ".env").read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def run_frontend_build() -> None:
    frontend_dir = BASE_DIR / "frontend"
    if (frontend_dir / "dist" / "index.html").exists() and "--rebuild" not in sys.argv:
        print("frontend/dist уже собран — пропускаем (флаг --rebuild для пересборки).")
        return
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    npm_path = shutil.which(npm_cmd) or shutil.which("npm")
    if npm_path is None:
        print(
            "ВНИМАНИЕ: npm не найден — фронт не собран, API всё равно запустится. "
            "Установите Node.js 18+ и выполните: cd frontend && npm install && npm run build"
        )
        return
    if not (frontend_dir / "node_modules").exists():
        print("Ставим зависимости фронта (npm install)...")
        subprocess.run([npm_path, "install"], cwd=str(frontend_dir), check=True)
    subprocess.run([npm_path, "run", "build"], cwd=str(frontend_dir), check=True)


def main() -> None:
    args = [arg.lower() for arg in sys.argv[1:]]
    env = "dev" if "dev" in args else "prod"
    os.environ["APP_ENV"] = env

    _load_env_file()

    if env == "prod":
        run_frontend_build()

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=(env == "dev"),
        reload_dirs=[str(BASE_DIR)] if env == "dev" else None,
    )


if __name__ == "__main__":
    main()
