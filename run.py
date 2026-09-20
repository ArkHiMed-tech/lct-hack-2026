import os
import sys

import uvicorn


def main() -> None:
    env = "dev" if len(sys.argv) > 1 and sys.argv[1].lower() == "dev" else "prod"
    os.environ["APP_ENV"] = env

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=(env == "dev"),
        reload_dirs=["."] if env == "dev" else None,
    )


if __name__ == "__main__":
    main()
