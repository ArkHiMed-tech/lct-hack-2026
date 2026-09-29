"""Ручки генератора карточек: граф + обход = данные карточки."""
from __future__ import annotations

from fastapi import APIRouter, Query

from misc.card_graph import (
    CARD_GRAPH,
    describe_graph,
    generate_batch,
    generate_card,
    next_node,
    next_options,
)

router = APIRouter(prefix="/api/cards", tags=["cards"])


@router.get("/graph")
async def card_graph():
    """Схема графа карточки: узлы, потоки, условные рёбра."""
    return {"graph": CARD_GRAPH, "flow": describe_graph()}


@router.get("/next")
async def card_next(path: str | None = Query(default=None)):
    """Следующие опции обхода по текущему пути 'a>b>c' (как /api/incident-tree)."""
    from misc.incident_tree_api import get_incident_next_levels

    if not path:
        return {"path": [], "next_node": "type", "options": next_options("type", {"tags": {}})}
    parts = [p for p in path.split(">") if p.strip()]
    # восстанавливаем минимальный ctx из пути: первый элемент = тип
    ctx: dict = {"tags": {}, "type": parts[0] if parts else "", "kind": "generic"}
    try:
        from misc.incident_tree_api import get_type_meta, load_incident_graph

        meta = get_type_meta(load_incident_graph(), ctx["type"]) or {}
        ctx["kind"] = meta.get("kind", "generic")
        # остаток пути — значения ТЭГов по порядку flow
        from misc.card_graph import FIRE101_FLOW, GENERIC_FLOW

        flow = FIRE101_FLOW if ctx["kind"] == "fire101" else GENERIC_FLOW
        for key, val in zip(flow, parts[1:]):
            ctx["tags"][key] = val
    except Exception:
        pass
    # текущий узел = последний заполненный + следующий
    node = "type"
    # идём по flow пока значения есть
    from misc.card_graph import FIRE101_FLOW, GENERIC_FLOW

    flow = FIRE101_FLOW if ctx["kind"] == "fire101" else GENERIC_FLOW
    last = "type"
    for key in flow:
        if key in ctx["tags"]:
            last = key
        else:
            break
    nxt = next_node(last, ctx)
    incident = get_incident_next_levels(path=path)
    return {
        "path": parts,
        "current": last,
        "next_node": nxt,
        "options": next_options(nxt, ctx) if nxt not in (None, "DONE") else [],
        "incident_tree": {"next_levels": incident["next_levels"], "is_leaf": incident["is_leaf"]},
    }


@router.get("/generate")
async def cards_generate(
    count: int = Query(default=1, ge=1, le=50),
    seed: int | None = Query(default=None),
    incident_type: str | None = Query(default=None),
):
    """Сгенерировать N карточек: каждая = один обход графа."""
    if count == 1:
        return generate_card(seed=seed, incident_type=incident_type)
    return {"count": count, "seed": seed, "cards": generate_batch(count, seed=seed, incident_type=incident_type)}


@router.post("/generate")
async def cards_generate_post(payload: dict):
    """POST-вариант: {"count","seed","incident_type","user_id"}."""
    count = int(payload.get("count", 1))
    count = max(1, min(50, count))
    seed = payload.get("seed")
    incident_type = payload.get("incident_type")
    user_id = payload.get("user_id")
    if count == 1:
        return generate_card(seed=seed, incident_type=incident_type, user_id=user_id)
    from misc.card_graph import walk, to_report_payload
    import random

    rng = random.Random(seed)
    return {
        "count": count,
        "seed": seed,
        "cards": [
            to_report_payload(walk(seed=rng.randint(0, 2 ** 31 - 1), fixed_type=incident_type), user_id=user_id)
            for _ in range(count)
        ],
    }
