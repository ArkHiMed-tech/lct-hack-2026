import asyncio
import json
import os
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from database import DB_PATH, FRONTEND_DIST, initialize_database, initialize_dev_data
from misc.incident_tree_api import get_incident_next_levels, get_incident_types, load_incident_graph
from misc.tts_service import TTSService
from routers.auth import router as auth_router
from routers.classifier import router as classifier_router
from routers.connection import router as connection_router
from routers.reports import router as reports_router
from routers.results import router as results_router
from routers.roles import router as roles_router
from routers.rubrics import router as rubrics_router
from routers.scenarios import router as scenarios_router
from routers.sessions import router as sessions_router
from routers.users import router as users_router

from asr.asr_service import get_asr_service
load_dotenv(Path(__file__).with_name(".env"))


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


app.include_router(auth_router)
app.include_router(classifier_router)
app.include_router(users_router)
app.include_router(roles_router)
app.include_router(scenarios_router)
app.include_router(rubrics_router)
app.include_router(sessions_router)
app.include_router(connection_router)
app.include_router(results_router)
app.include_router(reports_router)

MAP_BOUNDS = (36.8, 55.5, 37.97, 56.0)
MAP_FEATURE_QUERIES = {
    "water": (
        "Москва-река, Москва",
        "река Яуза, Москва",
        "река Сходня, Москва",
        "Химкинское водохранилище, Москва",
    ),
    "forest": (
        "Лосиный остров, Москва",
        "Битцевский лес, Москва",
        "Измайловский лесопарк, Москва",
        "Кузьминский лесопарк, Москва",
    ),
}


def _read_yandex_response(url: str) -> dict:
    try:
        with urlopen(url, timeout=8) as response:
            return json.load(response)
    except HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Яндекс.Карты вернули HTTP {exc.code}",
        ) from exc
    except URLError as exc:
        timed_out = (
            isinstance(exc.reason, TimeoutError)
            or getattr(exc.reason, "winerror", None) == 10060
        )
        if timed_out:
            raise HTTPException(
                status_code=504,
                detail="Таймаут соединения с Яндекс.Картами",
            ) from exc
        raise HTTPException(
            status_code=502, detail="Не удалось подключиться к Яндекс.Картам"
        ) from exc
    except (TimeoutError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=504 if isinstance(exc, TimeoutError) else 502,
            detail=(
                "Таймаут соединения с Яндекс.Картами"
                if isinstance(exc, TimeoutError)
                else "Яндекс.Карты вернули некорректный ответ"
            ),
        ) from exc


def _fetch_yandex_geocoder(api_key: str, query: str, kind: str | None = None) -> dict:
    request_params = {
        "apikey": api_key,
        "geocode": query,
        "lang": "ru_RU",
        "format": "json",
        "results": 1,
    }
    if kind:
        request_params["kind"] = kind
    params = urlencode(request_params)
    url = f"https://geocode-maps.yandex.ru/v1/?{params}"
    return _read_yandex_response(url)


def _find_okrug(metadata: dict, address: str) -> str | None:
    components = metadata.get("Address", {}).get("Components", [])
    component_names = [
        component.get("name", "").strip()
        for component in components
        if component.get("name")
    ]
    address_parts = [part.strip() for part in address.split(",")]
    for name in component_names + address_parts:
        normalized = name.casefold()
        if "округ" in normalized or name.upper().endswith("АО"):
            return name
    return None


@app.get("/api/map_valid")
async def valid_map(
    type: Literal["house", "street", "water", "forest"],
) -> dict:
    is_address_type = type in ("house", "street")
    api_key = os.getenv("YANDEX_GEOCODER_API_KEY") or os.getenv("YANDEX_MAPS_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Не задан ключ YANDEX_GEOCODER_API_KEY (или YANDEX_MAPS_API_KEY)",
        )

    if is_address_type:
        min_longitude, min_latitude, max_longitude, max_latitude = MAP_BOUNDS
        longitude = random.uniform(min_longitude, max_longitude)
        latitude = random.uniform(min_latitude, max_latitude)
        result = await asyncio.to_thread(
            _fetch_yandex_geocoder, api_key, f"{longitude},{latitude}", type
        )
    else:
        query = random.choice(MAP_FEATURE_QUERIES[type])
        result = await asyncio.to_thread(_fetch_yandex_geocoder, api_key, query)

    members = (
        result.get("response", {})
        .get("GeoObjectCollection", {})
        .get("featureMember", [])
    )

    if not is_address_type:
        for member in members:
            position = (
                member.get("GeoObject", {}).get("Point", {}).get("pos", "").split()
            )
            if len(position) == 2:
                longitude, latitude = map(float, position)
                return {
                    "type": type,
                    "coordinates": {"latitude": latitude, "longitude": longitude},
                }
        raise HTTPException(
            status_code=404,
            detail=f"Объект типа '{type}' не найден в выбранной области",
        )

    for member in members:
        geo_object = member.get("GeoObject", {})
        metadata = geo_object.get("metaDataProperty", {}).get("GeocoderMetaData", {})
        if metadata.get("kind") != type:
            continue

        address = metadata.get("Address", {}).get("formatted")
        if address:
            okrug = _find_okrug(metadata, address)
            if okrug and okrug.casefold() not in address.casefold():
                address = f"{address}, {okrug}"
            return {"type": type, "address": address, "okrug": okrug}

    raise HTTPException(
        status_code=404,
        detail=f"Объект типа '{type}' не найден в выбранной области",
    )


app.frontend("/", directory=str(FRONTEND_DIST))
