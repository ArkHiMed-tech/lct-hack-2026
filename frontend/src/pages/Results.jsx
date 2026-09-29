import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import { VERDICT_LABELS } from '../lib/scoring';
import { categoryLabel, serviceLabel } from '../lib/meta';

const SESSION_KEY = 'sim112-last-result';
// Пороги вердикта — зеркало бэкенда POST /api/sessions/finish.
const THRESHOLDS = { excellent: 85, pass: 60 };

function ScoreGauge({ score }) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(100, Number(score) || 0));
  const offset = c - (c * pct) / 100;
  const tone = pct >= THRESHOLDS.excellent ? 'ok' : pct >= THRESHOLDS.pass ? 'warn' : 'bad';

  return (
    <div className="score-gauge" data-tone={tone}>
      <svg viewBox="0 0 140 140" width="150" height="150" role="img" aria-label={`Итоговый балл ${Math.round(pct)} процентов`}>
        <circle className="gauge-bg" cx="70" cy="70" r={r} />
        <circle
          className="gauge-arc"
          cx="70"
          cy="70"
          r={r}
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="gauge-label">
        <strong>{Math.round(pct)}%</strong>
        <span>итоговый балл</span>
      </div>
    </div>
  );
}

function fmtLatency(sec) {
  if (sec == null || Number.isNaN(Number(sec))) return '—';
  return `${Number(sec).toFixed(1)} с`;
}

function SpeakerTag({ sender }) {
  return (
    <span className={`feed-speaker feed-${sender}`}>
      {sender === 'citizen' ? 'Абонент' : sender === 'operator' ? 'Диспетчер' : 'Система'}
    </span>
  );
}

// Крит. ошибки бэкенд присылает объектами {id, group, title} — рендерим по title с фолбэком.
function critText(c) {
  if (c == null) return '';
  if (typeof c === 'string') return c;
  return c.title ? `[${c.group ?? '?'} · ${c.id ?? '?'}] ${c.title}` : String(c.id ?? JSON.stringify(c));
}

const FORM_LABELS = {
  what: 'Что произошло',
  incident_category: 'Категория',
  address: 'Адрес',
  time: 'Время происшествия',
  caller_name: 'Заявитель',
  victims: 'Пострадавшие',
  conditions: 'Состояние',
  threat: 'Угроза жизни',
  factors: 'Опасные факторы',
  actions: 'Действия абонента',
  landmarks: 'Ориентиры',
  phone: 'Телефон',
};
function fmtFormValue(v) {
  if (v == null) return '—';
  if (Array.isArray(v)) return v.length ? v.join(', ') : '—';
  return String(v).trim() === '' ? '—' : String(v);
}

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user } = useAuth();

  const raw = useMemo(() => {
    if (location.state?.result) return location.state;
    try {
      const saved = sessionStorage.getItem(SESSION_KEY);
      return saved ? { result: JSON.parse(saved) } : null;
    } catch {
      return null;
    }
  }, [location.state]);

  // Рубрика — для названий критериев и привязки баллов к группам.
  const [rubric, setRubric] = useState(null);
  useEffect(() => {
    const rid = raw?.result?.rubric_id;
    if (!rid) return;
    let cancelled = false;
    fetch(`/data/rubrics/${rid}.json`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => { if (!cancelled) setRubric(data); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [raw]);

  useEffect(() => {
    if (!raw) navigate('/', { replace: true });
  }, [raw, navigate]);

  const groupRows = useMemo(() => {
    if (!raw) return [];
    const { result } = raw;
    const scores = result.scores ?? {};
    const meta = result.groups_meta ?? {};
    // item_id -> группа: из рубрики, иначе по первому символу id.
    const byRubric = {};
    (rubric?.groups ?? []).forEach((g) => (g.items ?? []).forEach((it) => { byRubric[it.id] = g.id; }));
    const buckets = {};
    Object.entries(scores).forEach(([itemId, score]) => {
      const gid = byRubric[itemId] ?? String(itemId).charAt(0);
      (buckets[gid] = buckets[gid] || []).push(Number(score) || 0);
    });
    const weights = rubric?.group_weights ?? {};
    return Object.keys({ ...meta, ...buckets }).sort().map((gid) => {
      const arr = buckets[gid] ?? [];
      const avg = arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : null;
      return {
        id: gid,
        title: meta[gid]?.title ?? rubric?.groups?.find((g) => g.id === gid)?.title ?? gid,
        passed: meta[gid]?.passed,
        weight: weights[gid],
        avg,
        count: arr.length,
      };
    });
  }, [raw, rubric]);

  const criteriaRows = useMemo(() => {
    if (!raw) return [];
    const { result } = raw;
    const scores = result.scores ?? {};
    const failed = new Set((result.failed_items ?? []).map((f) => f.id));
    const crit = new Set(rubric?.critical ?? []);
    const titleOf = {};
    const weightOf = {};
    (rubric?.groups ?? []).forEach((g) => (g.items ?? []).forEach((it) => {
      titleOf[it.id] = it.title;
      weightOf[it.id] = it.weight;
    }));
    // Все критерии из баллов + проваленные без баллов (на случай рассинхрона).
    const ids = [...new Set([...Object.keys(scores), ...(result.failed_items ?? []).map((f) => f.id)])];
    return ids.map((id) => {
      const fromFail = (result.failed_items ?? []).find((f) => f.id === id) ?? {};
      return {
        id,
        group: fromFail.group ?? String(id).charAt(0),
        title: titleOf[id] ?? fromFail.title ?? id,
        weight: weightOf[id],
        score: scores[id] ?? 0,
        failed: failed.has(id),
        critical: crit.has(id),
      };
    }).sort((a, b) => String(a.group).localeCompare(String(b.group)) || String(a.id).localeCompare(String(b.id)));
  }, [raw, rubric]);

  if (!raw) return null;

  const { result, scenario } = raw;
  const failedCount = result.failed_items?.length ?? 0;
  const critCount = result.critical_failures?.length ?? 0;
  const verdictTone =
    result.verdict === 'excellent' ? 'verdict-ok' : result.verdict === 'pass' ? 'verdict-warn' : 'verdict-bad';
  const latencyOk = result.answer_latency_sec != null && Number(result.answer_latency_sec) <= 8;
  const formEntries = Object.entries(result.form ?? {}).filter(([k]) => !['incident_category'].includes(k) || true);

  return (
    <div className="app-shell results-print-root">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content results-content">
          <div className="dds-back no-print">
            <Link to="/">← К списку происшествий</Link>
            <Link to="/journal">В журнал</Link>
          </div>

          <header className="results-head">
            <div>
              <h1>{scenario?.title ?? 'Результаты тренировки'}</h1>
              {scenario && (
                <p>
                  Категория: {categoryLabel(scenario.category)} · Рубрика «{result.rubric_id}»
                  {result.session_id != null ? ` · Сессия №${result.session_id}` : ''}
                </p>
              )}
              {result.detail && <p className="results-detail">{result.detail}</p>}
            </div>
            <span className={`verdict-chip ${verdictTone}`}>{VERDICT_LABELS[result.verdict] ?? result.verdict}</span>
          </header>

          <div className="results-layout">
            <div className="results-left">
              <ScoreGauge score={result.total_score} />
              <p className="results-thresholds">
                Пороги: ≥{THRESHOLDS.excellent}% — отлично · ≥{THRESHOLDS.pass}% — зачтено · ниже — не зачтено
              </p>

              <dl className="results-stats">
                <div>
                  <dt>Время ответа</dt>
                  <dd className={latencyOk ? 'stat-ok' : 'stat-bad'}>
                    {fmtLatency(result.answer_latency_sec)} <small>(норматив ≤ 8 с)</small>
                  </dd>
                </div>
                <div>
                  <dt>Передано служб ({result.dispatched_services?.length ?? 0})</dt>
                  <dd>{result.dispatched_services?.length ? result.dispatched_services.map(serviceLabel).join(', ') : '—'}</dd>
                </div>
                <div>
                  <dt>Невыполнено критериев</dt>
                  <dd className={failedCount ? 'critical-text' : ''}>{failedCount || 'нет'}</dd>
                </div>
                <div>
                  <dt>Критические ошибки</dt>
                  <dd className={critCount ? 'critical-text' : ''}>
                    {critCount ? result.critical_failures.map((c, i) => <div key={i}>{critText(c)}</div>) : 'нет'}
                  </dd>
                </div>
              </dl>

              <div className="results-actions no-print">
                <button type="button" className="btn btn-primary" onClick={() => navigate(`/scenario/${result.scenario_id}`)}>
                  Повторить тренировку
                </button>
                <button type="button" className="btn btn-ghost" onClick={() => window.print()}>
                  🖨 Печать / PDF
                </button>
                <Link to="/" className="btn btn-ghost">На главную</Link>
              </div>
            </div>

            <div className="results-right">
              <h2 className="block-title">Оценка по группам протокола</h2>
              {groupRows.length ? (
                <div className="results-groups">
                  {groupRows.map((g) => (
                    <div key={g.id} className="results-group-row">
                      <span className="results-group-title">
                        {g.id} · {g.title}
                        {g.weight != null && <small> · вес {Math.round(g.weight * 100)}%</small>}
                      </span>
                      <div className="checklist-bar" role="img" aria-label={`${g.title}: ${g.avg == null ? 'нет данных' : `${Math.round(g.avg)} процентов`}`}>
                        <div
                          className={`checklist-bar-fill ${g.avg >= 99 ? 'done' : g.avg >= 50 ? 'partial' : ''}`}
                          style={{ width: `${g.avg == null ? 0 : g.avg}%` }}
                        />
                      </div>
                      <span className="results-group-score">{g.avg == null ? '—' : `${Math.round(g.avg)}%`}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="results-empty">Нет данных по группам.</p>
              )}

              <h2 className="block-title">Невыполненные критерии ({failedCount})</h2>
              {failedCount ? (
                <ul className="failed-list">
                  {result.failed_items.map((f) => (
                    <li key={f.id}>
                      <strong>[{f.group} · {f.id}]</strong> {f.title}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="results-empty">Все активные критерии выполнены.</p>
              )}

              <h2 className="block-title">Все критерии ({criteriaRows.length})</h2>
              {criteriaRows.length ? (
                <div className="table-wrap results-table-wrap">
                  <table className="data-table results-table">
                    <thead>
                      <tr><th>Гр.</th><th>ID</th><th>Критерий</th><th>Балл</th><th>Статус</th></tr>
                    </thead>
                    <tbody>
                      {criteriaRows.map((c) => (
                        <tr key={c.id} className={c.failed ? 'row-failed' : ''}>
                          <td>{c.group}</td>
                          <td>{c.id}{c.critical ? ' ⚠' : ''}</td>
                          <td className="wrap">{c.title}</td>
                          <td>{Math.round(c.score)}%</td>
                          <td>{c.failed ? <span className="verdict-mini v-bad">провал</span> : <span className="verdict-mini v-ok">ок</span>}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="results-empty">Нет данных по критериям.</p>
              )}

              <h2 className="block-title">Заполненная карточка вызова</h2>
              {formEntries.length ? (
                <dl className="results-form">
                  {formEntries.map(([k, v]) => (
                    <div key={k}>
                      <dt>{FORM_LABELS[k] ?? k}</dt>
                      <dd>{fmtFormValue(v)}</dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="results-empty">Карточка не заполнялась.</p>
              )}

              <h2 className="block-title">Диалог вызова ({(result.messages ?? []).length})</h2>
              {(result.messages ?? []).length ? (
                <div className="results-dialog">
                  {result.messages.map((m, i) => (
                    <div key={i} className={`feed-row feed-${m.sender}`}>
                      <SpeakerTag sender={m.sender} />
                      {m.emotion && <span className="feed-emotion">{m.emotion}</span>}
                      {m.time && <span className="feed-time">{m.time}</span>}
                      <p>{m.text}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="results-empty">Сообщений нет.</p>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
