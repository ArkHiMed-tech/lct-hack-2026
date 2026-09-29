"""API классификатора происшествий (дерево xlsx, секция classifier графа v2).

Тип происшествия карточки — Итоговый тип классификатора (Номер + путь
Признак1→Признак2→Признак3), а не номера служб 101/102/103/104.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from misc.incident_tree_api import (
    compact_leaf,
    dispatch_for_leaf,
    get_classifier,
    get_leaf_by_code,
    load_incident_graph,
    search_leaves,
    service_display_name,
)

router = APIRouter(prefix="/api/classifier", tags=["classifier"])


def _sections_map(graph: dict) -> dict[int, str]:
    return {s["g"]: s["title"] for s in get_classifier(graph).get("sections", [])}


@router.get("/sections")
async def list_sections():
    graph = load_incident_graph()
    classifier = get_classifier(graph)
    sections = classifier.get("sections", [])
    counts: dict[int, int] = {}
    groups: dict[int, list[str]] = {}
    for leaf in classifier.get("leaves", []) or []:
        counts[leaf["g"]] = counts.get(leaf["g"], 0) + 1
        if leaf.get("group") not in (groups.get(leaf["g"]) or []):
            groups.setdefault(leaf["g"], []).append(leaf.get("group"))
    return [
        {
            "g": s["g"],
            "title": s["title"],
            "filled": s.get("filled", False),
            "leaf_count": counts.get(s["g"], 0),
            "groups": groups.get(s["g"], []),
        }
        for s in sections
    ]


@router.get("/leaves")
async def list_leaves(
    g: int | None = Query(default=None),
    visible_only: bool = Query(default=True),
    limit: int = Query(default=1000, ge=1, le=2000),
):
    graph = load_incident_graph()
    sections = _sections_map(graph)
    out = []
    for leaf in get_classifier(graph).get("leaves", []) or []:
        if g is not None and leaf.get("g") != g:
            continue
        if visible_only and not leaf.get("operator_visible", True):
            continue
        out.append(compact_leaf(leaf, sections))
        if len(out) >= limit:
            break
    return {"count": len(out), "items": out}


@router.get("/search")
async def search(
    q: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
):
    return {"query": q, "items": search_leaves(limit=limit, query=q)}


@router.get("/leaf/{code}")
async def get_leaf(code: str):
    graph = load_incident_graph()
    leaf = get_leaf_by_code(graph, code)
    if leaf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leaf not found"
        )
    sections = _sections_map(graph)
    return {"leaf": compact_leaf(leaf, sections), "extra": leaf.get("extra")}


@router.get("/dispatch")
async def dispatch(
    code: str = Query(...),
    nd: bool = False,
    ul: bool = False,
    pp: bool = False,
    violation: bool = False,
    victims: bool = False,
    victims_absent: bool = False,
    gas: bool = False,
    threat: bool = False,
    medical: bool = False,
    evac: bool = False,
    crowd: bool = False,
    block: bool = False,
    tunnel: bool = False,
    pesh: bool = False,
    av: bool = False,
    sites: bool = False,
    stroyka: bool = False,
):
    graph = load_incident_graph()
    leaf = get_leaf_by_code(graph, code)
    if leaf is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Leaf not found"
        )
    flags = {
        "nd": nd, "ul": ul, "pp": pp, "violation": violation,
        "victims": victims, "victims_absent": victims_absent, "gas": gas,
        "threat": threat, "medical": medical, "evac": evac, "crowd": crowd,
        "block": block, "tunnel": tunnel, "pesh": pesh, "av": av,
        "sites": sites, "stroyka": stroyka,
    }
    disp = dispatch_for_leaf(graph, leaf, flags)
    # Главные службы (101/102/103/104/ЦЭМП) — первыми.
    priority = {"mchs101": 0, "mvd": 1, "smp": 2, "mosgaz": 3, "cemp": 4}
    ordered = sorted(disp, key=lambda gid: (priority.get(gid, 99), gid))
    return {
        "code": leaf["code"],
        "services": [service_display_name(graph, gid) for gid in ordered],
        "detail": {
            gid: {"value": value, "display": service_display_name(graph, gid)}
            for gid, value in disp.items()
        },
    }
