import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from database import DB_PATH, FRONTEND_DIST, initialize_database, initialize_dev_data
from routers.auth import router as auth_router
from routers.reports import router as reports_router
from routers.results import router as results_router
from routers.roles import router as roles_router
from routers.rubrics import router as rubrics_router
from routers.scenarios import router as scenarios_router
from routers.sessions import router as sessions_router
from routers.users import router as users_router

app = FastAPI(title="LCT Hack 2026 API")


@app.on_event("startup")
async def startup_event() -> None:
    env = os.getenv("APP_ENV", "prod").lower()
    if env == "dev":
        initialize_dev_data()
    else:
        initialize_database()


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app_env": os.getenv("APP_ENV", "prod"),
        "frontend_build_exists": FRONTEND_DIST.exists(),
        "database_exists": DB_PATH.exists(),
    }


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(scenarios_router)
app.include_router(rubrics_router)
app.include_router(sessions_router)
app.include_router(results_router)
app.include_router(reports_router)


if FRONTEND_DIST.exists():

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")

        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)

        return FileResponse(FRONTEND_DIST / "index.html")
