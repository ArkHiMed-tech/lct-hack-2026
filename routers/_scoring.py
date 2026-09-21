"""Общий скоринг тренировки (порт frontend/src/lib/scoring.js).

Используется ручками POST /api/sessions/draft (черновик, без записи в БД)
и POST /api/sessions/finish (финал, с записью в БД).

Возвращаемая форма совместима с прежним computeDraftResult, чтобы
фронтенд без lib/scoring.js мог рисовать прогресс и страницу результатов:
  scores: {group_id: 0..1}, total_score: 0..100, groups_meta: [{id, title}], ...
"""

from __future__ import annotations

import time


def _norm(value) -> str:
    return str(value if value is not None else "").strip().lower()


def _non_empty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, list):
        return len(value) > 0
    return _norm(value) != ""


def _includes_any(text: str, terms) -> bool:
    ntext = _norm(text)
    return any(_norm(term) in ntext for term in terms)


def _any_group_matches(text: str, terms) -> bool:
    return any(_includes_any(text, group) for group in terms)


def _match_terms(text: str, terms, any_flag: bool = False) -> bool:
    if not terms:
        return True
    if any_flag:
        return _any_group_matches(text, terms)
    return all(_includes_any(text, group) for group in terms)


def _address_tokens(scenario: dict) -> list:
    expected = (scenario or {}).get("expected", {}) or {}
    address = expected.get("address", {}) or {}
    return [v for v in (address.get("street"), address.get("house"), address.get("city"), address.get("flat")) if v]


def _operator_texts(messages) -> list:
    return [m.get("text", "") for m in (messages or []) if isinstance(m, dict) and m.get("sender") == "operator"]


def _evaluate_item(item: dict, ctx: dict):
    session = ctx["session"]
    scenario = ctx["scenario"]
    user = ctx["user"]
    form = session.get("form") or {}
    messages = session.get("messages") or []
    operator_texts = _operator_texts(messages)
    first_operator = operator_texts[0] if operator_texts else ""
    check = item.get("check")

    if check == "timing":
        latency = session.get("answerLatencySec")
        if latency is None:
            return False
        try:
            return float(latency) <= float(item.get("target_sec", 8))
        except (TypeError, ValueError):
            return False

    if check == "text_first":
        return _match_terms(first_operator, item.get("terms"), bool(item.get("any", False)))

    if check == "text_any_operator":
        return any(_match_terms(t, item.get("terms"), bool(item.get("any", False))) for t in operator_texts)

    if check == "self_intro":
        last = _norm((user or {}).get("last_name", ""))
        return bool(last) and last in _norm(first_operator)

    if check == "form":
        return _non_empty(form.get(item.get("field")))

    if check == "phone_known":
        call = session.get("call") or {}
        return _non_empty(form.get("phone")) or _non_empty(call.get("phone"))

    if check == "address_complete":
        tokens = _address_tokens(scenario)
        if not tokens:
            return None
        addr = _norm(form.get("address", ""))
        return all(_norm(t) in addr for t in tokens)

    if check == "address_confirmation":
        tokens = _address_tokens(scenario)
        if not tokens:
            return None
        return any(_match_terms(t, [tokens[:3]], False) for t in operator_texts)

    if check == "count_match":
        expected = _norm(((scenario or {}).get("expected", {}) or {}).get("victims_count", ""))
        if not expected:
            return None
        val = _norm(form.get("victims", ""))
        if not val:
            return False
        return val in expected or expected in val

    if check == "category_match":
        return (form.get("incident_category", "") or "") == ((scenario or {}).get("expected", {}) or {}).get("incident_category")

    if check == "service_match":
        expected = set(((scenario or {}).get("expected", {}) or {}).get("expected_services", []) or [])
        chosen = set(session.get("services") or [])
        if not expected:
            return _non_empty(session.get("services"))
        if len(expected) != len(chosen):
            return False
        return all(s in expected for s in chosen)

    if check == "form_complete":
        required = (scenario or {}).get("required_fields") or []
        if not required:
            return None
        filled = sum(1 for f in required if _non_empty(form.get(f)))
        return filled / len(required)

    if check == "description_length":
        what = _norm(form.get("what", ""))
        if not what:
            return False
        return len(what) <= 300

    if check == "timestamps":
        return bool(session.get("callStartedAtMs") and session.get("endedAtMs"))

    if check == "dispatch_before_end":
        dispatched = session.get("dispatched")
        ended = session.get("endedAtMs")
        dispatched_at = session.get("dispatchedAtMs")
        return bool(dispatched and ended and dispatched_at is not None and dispatched_at <= ended)

    if check == "hang_after_dispatch":
        dispatched_at = session.get("dispatchedAtMs")
        ended = session.get("endedAtMs")
        return bool(dispatched_at is not None and ended is not None and dispatched_at <= ended)

    return None


def _evaluate_criticals(ctx: dict) -> list:
    session = ctx["session"]
    scenario = ctx["scenario"]
    messages = session.get("messages") or []
    operator_texts = _operator_texts(messages)
    first = operator_texts[0] if operator_texts else ""
    criticals = []

    greeted = _match_terms(first, [["112", "служба спасения", "единая служба"], ["слушаю"]], False)
    if not greeted:
        criticals.append("X1")

    addr = _norm((session.get("form") or {}).get("address", ""))
    tokens = [t for t in _address_tokens(scenario) if t]
    if tokens and not all(_norm(t) in addr for t in tokens):
        criticals.append("X2")

    services = session.get("services") or []
    if not services:
        criticals.append("X3")
    else:
        expected = set(((scenario or {}).get("expected", {}) or {}).get("expected_services", []) or [])
        if expected and not any(s in expected for s in services):
            criticals.append("X4")

    if session.get("endedAtMs") and not session.get("dispatchedAtMs"):
        criticals.append("X6")

    return criticals


def compute_result(session: dict, scenario: dict, rubric: dict, user: dict | None = None) -> dict:
    """Полный расчёт результата. Формат как у прежнего computeDraftResult."""
    user = user or {}
    group_scores: dict = {}
    failed_items: list = []
    detail: dict = {}

    for group in rubric.get("groups", []):
        active = list(group.get("items", []))

        if group.get("id") == "D":
            subset = (rubric.get("category_subsets", {}) or {}).get((scenario or {}).get("category"), []) or []
            active = [it for it in active if it.get("id") in subset]

        ctx = {"session": session, "scenario": scenario or {}, "user": user}
        raw = 0.0
        total_weight = 0.0
        per_item = []
        for item in active:
            raw_score = _evaluate_item(item, ctx)
            if raw_score is None or raw_score is True:
                score = 1.0
            elif raw_score is False:
                score = 0.0
            else:
                score = float(raw_score)
            weight = float(item.get("weight", 0.0))
            raw += score * weight
            total_weight += weight
            per_item.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "achieved": score == 1.0,
                    "score": score,
                    "weight": weight,
                }
            )
            if score != 1.0:
                failed_items.append(
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "score": score,
                        "weight": weight,
                        "group": group.get("id"),
                    }
                )

        group_scores[group.get("id")] = (raw / total_weight) if total_weight else 0.0
        detail[group.get("id")] = per_item

    weights = rubric.get("group_weights", {}) or {}
    total = sum((group_scores.get(gid, 0.0)) * float(weights.get(gid, 0.0)) for gid in weights)
    total_score = round(total * 1000) / 10

    critical_set = _evaluate_criticals({"session": session, "scenario": scenario or {}, "user": user})
    has_critical = any(c in critical_set for c in (rubric.get("critical", []) or []))
    verdict = "fail" if (has_critical or total_score < 60) else ("excellent" if total_score >= 80 else "pass")

    return {
        "session_id": session.get("sessionId") or f"s-{int(time.time() * 1000)}",
        "scenario_id": (scenario or {}).get("id"),
        "rubric_id": rubric.get("id"),
        "groups_meta": [{"id": g.get("id"), "title": g.get("title")} for g in rubric.get("groups", [])],
        "answer_latency_sec": session.get("answerLatencySec"),
        "messages": session.get("messages") or [],
        "form": session.get("form") or {},
        "dispatched_services": session.get("services") or [],
        "scores": group_scores,
        "total_score": total_score,
        "verdict": verdict,
        "failed_items": failed_items,
        "critical_failures": critical_set,
        "detail": detail,
    }
