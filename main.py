import os
from contextlib import asynccontextmanager

<<<<<<< Updated upstream
from fastapi import FastAPI

<<<<<<< Updated upstream
from database import DB_PATH, FRONTEND_DIST, initialize_database, initialize_dev_data
=======
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
if 'test' in sys.argv:
    DB_PATH = BASE_DIR / "test_db.db"
else:
    DB_PATH = BASE_DIR / "db.db"

app = FastAPI(title="LCT Hack 2026 API")
=======
from fastapi import FastAPI, Query

from database import DB_PATH, FRONTEND_DIST, initialize_database, initialize_dev_data
from misc.incident_tree_api import get_incident_next_levels
>>>>>>> Stashed changes
from routers.auth import router as auth_router
from routers.connection import router as connection_router
from routers.reports import router as reports_router
from routers.results import router as results_router
from routers.roles import router as roles_router
from routers.rubrics import router as rubrics_router
from routers.scenarios import router as scenarios_router
from routers.sessions import router as sessions_router
from routers.users import router as users_router
<<<<<<< Updated upstream
=======
>>>>>>> Stashed changes
>>>>>>> Stashed changes


@asynccontextmanager
async def lifespan(_: FastAPI):
    env = os.getenv("APP_ENV", "prod").lower()
    if env == "dev":
        initialize_dev_data()
    else:
        initialize_database()
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


<<<<<<< Updated upstream
=======
<<<<<<< Updated upstream
@app.post("/api/users/create")
async def create_user(user: User):
    with get_connection() as connection:
        user_id = user.login.lower().replace(" ", "-") or user.email
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO users (
                id, login, password, email, name, last_name, role, group_name, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                user.login,
                user.password,
                user.email,
                user.name,
                user.last_name,
                user.role,
                user.group_name,
                int(user.active),
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM users WHERE login = ?",
            (user.login,),
        ).fetchone()
        return {
            "message": f"User {user.login} created",
            "info": dict(row) if row else None,
        }
=======
@app.get("/api/incident-tree")
async def incident_tree(
    group1: str | None = Query(default=None),
    group2: str | None = Query(default=None),
    group3: str | None = Query(default=None),
    group4: str | None = Query(default=None),
    path: str | None = Query(default=None),
):
    return get_incident_next_levels(
        group1=group1,
        group2=group2,
        group3=group3,
        group4=group4,
        path=path,
    )


>>>>>>> Stashed changes
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(scenarios_router)
app.include_router(rubrics_router)
app.include_router(sessions_router)
app.include_router(connection_router)
app.include_router(results_router)
app.include_router(reports_router)
<<<<<<< Updated upstream
=======
>>>>>>> Stashed changes
>>>>>>> Stashed changes

app.frontend("/", directory=str(FRONTEND_DIST))
