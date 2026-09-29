import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query

from database import DB_PATH, FRONTEND_DIST, initialize_database, initialize_dev_data
from misc.incident_tree_api import get_incident_next_levels, get_incident_types, load_incident_graph
from misc.tts_service import TTSService
from routers.auth import router as auth_router
from routers.connection import router as connection_router
from routers.reports import router as reports_router
from routers.results import router as results_router
from routers.roles import router as roles_router
from routers.rubrics import router as rubrics_router
from routers.scenarios import router as scenarios_router
from routers.sessions import router as sessions_router
from routers.users import router as users_router

from asr.asr_service import get_asr_service, transcribe_audio


@asynccontextmanager
async def lifespan(_: FastAPI):
    env = os.getenv("APP_ENV", "prod").lower()
    if env == "dev":
        initialize_dev_data()
    else:
        initialize_database()
    app.state.asr_service = await get_asr_service()
    app.state.asr_service = TTSService()
    yield


app = FastAPI(title="LCT Hack 2026 API", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "app_env": os.getenv("APP_ENV", "prod"),
        "frontend_build_exists": FRONTEND_DIST.exists(),
        "database_exists": DB_PATH.exists(),
    }


@app.get("/api/incident-tree")
async def incident_tree(
    group1: str | None = Query(default=None),
    group2: str | None = Query(default=None),
    group3: str | None = Query(default=None),
    group4: str | None = Query(default=None),
    group5: str | None = Query(default=None),
    group6: str | None = Query(default=None),
    group7: str | None = Query(default=None),
    group8: str | None = Query(default=None),
    path: str | None = Query(default=None),
):
    return get_incident_next_levels(
        group1=group1,
        group2=group2,
        group3=group3,
        group4=group4,
        group5=group5,
        group6=group6,
        group7=group7,
        group8=group8,
        path=path,
    )


@app.get("/api/incident-types")
async def incident_types():
    graph = load_incident_graph()
    return {"count": len(graph.get("root_children", [])), "items": get_incident_types(graph)}


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(scenarios_router)
app.include_router(rubrics_router)
app.include_router(sessions_router)
app.include_router(connection_router)
app.include_router(results_router)
app.include_router(reports_router)

app.frontend("/", directory=str(FRONTEND_DIST))
