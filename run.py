import importlib.util
import os
import shutil
import subprocess
import sys

# Автодоставка зависимостей при запуске (до импорта uvicorn,
# чтобы скрипт не падал на чистой машине).
REQUIRED_PACKAGES = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "cryptography": "cryptography",
}


def ensure_dependencies() -> None:
    missing = [
        pkg for pkg, module in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *missing],
            check=True,
        )


ensure_dependencies()

import uvicorn


def run_frontend_build() -> None:
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    npm_path = shutil.which(npm_cmd) or shutil.which("npm")
    subprocess.run([npm_path, "run", "build"], cwd=frontend_dir, check=True)


def main() -> None:
    env = "dev" if len(sys.argv) > 1 and sys.argv[1].lower() == "dev" else "prod"
    os.environ["APP_ENV"] = env

    if env == "prod":
        run_frontend_build()

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=(env == "dev"),
        reload_dirs=["."] if env == "dev" else None,
    )


if __name__ == "__main__":
    main()
