from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

app = FastAPI(title="LCT Hack 2026 API")


class User(BaseModel):
    login: str
    password: str
    email: str


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "frontend_build_exists": FRONTEND_DIST.exists(),
    }


@app.post("/api/users/create")
async def create_user(user: User):
    return {
        "message": f"User {user.login} created",
        "info": user.model_dump(mode="json"),
    }


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
