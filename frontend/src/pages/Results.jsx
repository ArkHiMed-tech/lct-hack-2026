import { useEffect, useMemo } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import { VERDICT_LABELS, categoryLabel, serviceLabel } from '../lib/meta';

const SESSION_KEY = 'sim112-last-result';

function ScoreGauge({ score }) {
  const r = 54;
  const c = 2 * Math.PI * r;
  const pct = Math.min(100, score);
  const offset = c - (c * pct) / 100;
  const tone = pct >= 80 ? 'ok' : pct >= 60 ? 'warn' : 'bad';

  return (
    <div className="score-gauge" data-tone={tone}>
      <svg viewBox="0 0 140 140" width="150" height="150">
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

function GroupScoreList({ scores, groups }) {
  return (
    <div className="results-groups">
      {Object.entries(scores).map(([gid, score]) => {
        const g = groups.find((x) => x.id === gid);
        return (
          <div key={gid} className="results-group-row">
            <span className="results-group-title">
              {gid} · {g?.title ?? gid}
            </span>
            <div className="checklist-bar">
              <div
                className={`checklist-bar-fill ${score >= 1 ? 'done' : score >= 0.5 ? 'partial' : ''}`}
                style={{ width: `${score * 100}%` }}
              />
            </div>
            <span className="results-group-score">{Math.round(score * 100)}%</span>
          </div>
        );
      })}
    </div>
  );
}

function SpeakerTag({ sender }) {
  return (
    <span className={`feed-speaker feed-${sender}`}>
      {sender === 'citizen' ? 'Абонент' : sender === 'operator' ? 'Диспетчер' : 'Система'}
    </span>
  );
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

  useEffect(() => {
    if (!raw) navigate('/', { replace: true });
  }, [raw, navigate]);

  if (!raw) return null;

  const { result, scenario } = raw;
  const groups = result.groups_meta ?? [];
  const verdictTone =
    result.verdict === 'excellent' ? 'verdict-ok' : result.verdict === 'pass' ? 'verdict-warn' : 'verdict-bad';

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content results-content">
          <header className="results-head">
            <div>
              <h1>{scenario?.title ?? 'Результаты тренировки'}</h1>
              {scenario && (
                <p>
                  Категория: {categoryLabel(scenario.category)} · Разбор по рубрике «{result.rubric_id}»
                </p>
              )}
            </div>
            <span className={`verdict-chip ${verdictTone}`}>{VERDICT_LABELS[result.verdict] ?? result.verdict}</span>
          </header>

          <div className="results-layout">
            <div className="results-left">
              <ScoreGauge score={result.total_score} />

              <div className="results-stats">
                <div>
                  <dt>Время ответа</dt>
                  <dd>{result.answer_latency_sec == null ? '—' : `${result.answer_latency_sec.toFixed(1)} с`}</dd>
                </div>
                <div>
                  <dt>Передано служб</dt>
                  <dd>{result.dispatched_services.length ? result.dispatched_services.map(serviceLabel).join(', ') : '—'}</dd>
                </div>
                <div>
                  <dt>Критические ошибки</dt>
                  <dd className={result.critical_failures.length ? 'critical-text' : ''}>
                    {result.critical_failures.length ? result.critical_failures.join(', ') : 'нет'}
                  </dd>
                </div>
              </div>

              <div className="results-actions">
                <button type="button" className="btn btn-primary" onClick={() => navigate(`/scenario/${result.scenario_id}`)}>
                  Повторить тренировку
                </button>
                <Link to="/" className="btn btn-ghost">
                  На главную
                </Link>
              </div>
            </div>

            <div className="results-right">
              <h2 className="block-title">Оценка по группам протокола</h2>
              <GroupScoreList scores={result.scores} groups={groups} />

              <h2 className="block-title">Невыполненные критерии</h2>
              {result.failed_items.length ? (
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

              <h2 className="block-title">Диалог вызова</h2>
              <div className="results-dialog">
                {(result.messages ?? []).map((m, i) => (
                  <div key={i} className={`feed-row feed-${m.sender}`}>
                    <SpeakerTag sender={m.sender} />
                    {m.emotion && <span className="feed-emotion">{m.emotion}</span>}
                    <p>{m.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}