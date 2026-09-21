// Черновой режим оценки ответов диспетчера (прототип).
// Авторитетный расчёт выполняется бэкендом; здесь — мгновенная обратная связь
// для интерфейса (см. JSON-CONTRACT.md, раздел «Правила интеграции»).

const norm = (s) => String(s ?? '').toLowerCase().trim();
const includesAny = (text, terms) => terms.some((t) => norm(text).includes(norm(t)));
const matchTerms = (text, terms, any) => {
  if (!terms || !terms.length) return true;
  return any ? anyGroupMatches(text, terms) : terms.every((g) => includesAny(text, g));
};
const anyGroupMatches = (text, terms) => terms.some((g) => includesAny(text, g));

const nonEmpty = (v) => {
  if (v == null) return false;
  if (Array.isArray(v)) return v.length > 0;
  return norm(v) !== '';
};

function addressTokens(scenario) {
  const a = scenario?.expected?.address ?? {};
  return [a.street, a.house, a.city, a.flat].filter(Boolean);
}

function ctxOf(session, scenario, user) {
  const operatorTexts = () => (session.messages ?? []).filter((m) => m.sender === 'operator').map((m) => m.text);
  const firstOperator = () => operatorTexts()[0] ?? '';
  return {
    session,
    scenario,
    user,
    firstOperator,
    allOperator: () => operatorTexts().join(' '),
    anyOperatorMsg: (terms, any) => operatorTexts().some((t) => matchTerms(t, terms, any)),
  };
}

function evaluateItem(item, ctx) {
  const { session, scenario, user } = ctx;
  const form = session.form ?? {};

  switch (item.check) {
    case 'timing':
      return (session.answerLatencySec ?? Infinity) <= (item.target_sec ?? 8);

    case 'text_first':
      return matchTerms(ctx.firstOperator(), item.terms, item.any ?? false);

    case 'text_any_operator':
      return ctx.anyOperatorMsg(item.terms, item.any ?? false);

    case 'self_intro': {
      const last = norm(user?.last_name ?? '');
      return last && norm(ctx.firstOperator()).includes(last);
    }

    case 'form':
      return nonEmpty(form[item.field]);

    case 'phone_known':
      return nonEmpty(form.phone) || nonEmpty(session.call?.phone);

    case 'address_complete': {
      const tokens = addressTokens(scenario);
      if (!tokens.length) return null;
      const addr = norm(form.address ?? '');
      return tokens.every((t) => addr.includes(norm(t)));
    }

    case 'address_confirmation': {
      const tokens = addressTokens(scenario);
      if (!tokens.length) return null;
      return ctx.anyOperatorMsg(
        [tokens.slice(0, 3)],
        false,
      );
    }

    case 'count_match': {
      const exp = norm(scenario?.expected?.victims_count ?? '');
      if (!exp) return null;
      const val = norm(form.victims ?? '');
      if (!val) return false;
      return val.includes(exp) || exp.includes(val);
    }

    case 'category_match':
      return (form.incident_category ?? '') === scenario?.expected?.incident_category;

    case 'service_match': {
      const expected = new Set(scenario?.expected?.expected_services ?? []);
      const chosen = new Set(session.services ?? []);
      if (!expected.size) return nonEmpty(session.services);
      if (expected.size !== chosen.size) return false;
      return [...chosen].every((s) => expected.has(s));
    }

    case 'form_complete': {
      const required = scenario?.required_fields ?? [];
      if (!required.length) return null;
      const filled = required.filter((f) => nonEmpty(form[f])).length;
      return filled / required.length;
    }

    case 'description_length': {
      const what = norm(form.what ?? '');
      if (!what) return false;
      return what.length <= 300;
    }

    case 'timestamps':
      return Boolean(session.callStartedAtMs && session.endedAtMs);

    case 'dispatch_before_end':
      return Boolean(
        session.dispatched && session.endedAtMs && session.dispatchedAtMs != null && session.dispatchedAtMs <= session.endedAtMs,
      );

    case 'hang_after_dispatch':
      return Boolean(
        session.dispatchedAtMs != null && session.endedAtMs != null && session.dispatchedAtMs <= session.endedAtMs,
      );

    default:
      return null;
  }
}

function isActive(item, scenario) {
  if (item.check === 'timestamps' && !scenario) return false;
  return true;
}

function evaluateCriticals(ctx) {
  const { session, scenario } = ctx;
  const criticals = [];

  const first = ctx.firstOperator();
  const answeredWithGreeting = matchTerms(first, [['112', 'служба спасения', 'единая служба'], ['слушаю']], false);
  if (!answeredWithGreeting) criticals.push('X1');

  const addr = norm(session.form?.address ?? '');
  const tokens = addressTokens(scenario).filter(Boolean);
  if (tokens.length && !tokens.every((t) => addr.includes(norm(t)))) criticals.push('X2');

  const services = session.services ?? [];
  if (!services.length) criticals.push('X3');
  else {
    const expected = new Set(scenario?.expected?.expected_services ?? []);
    if (expected.size && !services.some((s) => expected.has(s))) criticals.push('X4');
  }

  if (session.endedAtMs && !session.dispatchedAtMs) criticals.push('X6');

  return criticals;
}

export function computeDraftResult(session, scenario, rubric, user) {
  const ctx = ctxOf(session, scenario, user);
  const groupScores = {};
  const failedItems = [];
  const detail = {};

  for (const group of rubric.groups) {
    let active = group.items.filter((it) => isActive(it, scenario));

    if (group.id === 'D') {
      const subset = rubric.category_subsets?.[scenario?.category] ?? [];
      active = active.filter((it) => subset.includes(it.id));
    }

    let raw = 0;
    let totalWeight = 0;
    const perItem = [];

    active.forEach((item) => {
      const rawScore = evaluateItem(item, ctx);
      const score = rawScore == null || rawScore === true ? 1 : rawScore === false ? 0 : rawScore;
      raw += score * item.weight;
      totalWeight += item.weight;
      perItem.push({ id: item.id, title: item.title, achieved: score === 1, score, weight: item.weight });
      if (score !== 1 && score != null) {
        failedItems.push({ id: item.id, title: item.title, score, weight: item.weight, group: group.id });
      }
    });

    const groupScore = totalWeight ? raw / totalWeight : 0;
    groupScores[group.id] = groupScore;
    detail[group.id] = perItem;
  }

  const weights = rubric.group_weights ?? {};
  let total = 0;
  for (const id of Object.keys(weights)) {
    total += (groupScores[id] ?? 0) * (weights[id] ?? 0);
  }
  const totalScore = Math.round(total * 1000) / 10;

  const criticalSet = evaluateCriticals(ctx);
  const hasCritical = rubric.critical.some((c) => criticalSet.includes(c));

  const verdict =
    hasCritical || totalScore < 60 ? 'fail' : totalScore >= 80 ? 'excellent' : 'pass';

  return {
    session_id: session.sessionId ?? `s-${Date.now()}`,
    scenario_id: scenario?.id,
    rubric_id: rubric.id,
    groups_meta: rubric.groups.map((g) => ({ id: g.id, title: g.title })),
    answer_latency_sec: session.answerLatencySec ?? null,
    messages: session.messages ?? [],
    form: session.form ?? {},
    dispatched_services: session.services ?? [],
    scores: groupScores,
    total_score: totalScore,
    verdict,
    failed_items: failedItems,
    critical_failures: criticalSet,
    detail,
  };
}

export const VERDICT_LABELS = {
  excellent: 'Зачтено · отлично',
  pass: 'Зачтено',
  fail: 'Не зачтено',
};