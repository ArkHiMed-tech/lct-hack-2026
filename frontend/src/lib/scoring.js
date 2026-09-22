// Draft-превью оценки для живого чек-листа (ChecklistProgress в Simulator).
// Авторитетный расчёт выполняет ТОЛЬКО бэкенд POST /api/sessions/finish,
// фронт этот результат не строит, а лишь показывает (см. JSON-CONTRACT.md §8).
// Здесь — минимальный набор { scores, total_score } для мгновенной подсветки.
// Бэкенд не трогаем; пороги вердикта источника истины — на бэкенде.

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

export function computeDraftPreview(session, scenario, rubric, user) {
  const ctx = ctxOf(session, scenario, user);
  const groupScores = {};

  for (const group of rubric.groups) {
    let active = group.items.filter((it) => isActive(it, scenario));

    if (group.id === 'D') {
      const subset = rubric.category_subsets?.[scenario?.category] ?? [];
      active = active.filter((it) => subset.includes(it.id));
    }

    let raw = 0;
    let totalWeight = 0;

    active.forEach((item) => {
      const rawScore = evaluateItem(item, ctx);
      const score = rawScore == null || rawScore === true ? 1 : rawScore === false ? 0 : rawScore;
      raw += score * item.weight;
      totalWeight += item.weight;
    });

    groupScores[group.id] = totalWeight ? raw / totalWeight : 0;
  }

  const weights = rubric.group_weights ?? {};
  let total = 0;
  for (const id of Object.keys(weights)) {
    total += (groupScores[id] ?? 0) * (weights[id] ?? 0);
  }
  const totalScore = Math.round(total * 1000) / 10;

  // Только минимум для ChecklistProgress. Полный объект результата
  // (session_id, messages, form, failed_items, critical_failures, detail,
  // groups_meta, verdict по порогам бэкенда) строит POST /api/sessions/finish.
  return {
    scores: groupScores,
    total_score: totalScore,
  };
}

// Алиас для совместимости, чтобы не ломать существующие импорты.
export { computeDraftPreview as computeDraftResult };

export const VERDICT_LABELS = {
  excellent: 'Зачтено · отлично',
  pass: 'Зачтено',
  fail: 'Не зачтено',
};