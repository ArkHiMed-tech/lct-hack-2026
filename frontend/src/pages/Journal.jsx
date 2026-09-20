import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import useJson from '../hooks/useJson';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import PageTitle from '../components/PageTitle';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import { categoryLabel, formatScore } from '../lib/meta';

const VERDICT_TONES = { excellent: 'v-ok', pass: 'v-warn', fail: 'v-bad' };

export default function Journal() {
  const { user } = useAuth();
  const results = useJson('/data/results.json');
  const users = useJson('/data/users.json');
  const catalog = useJson('/data/scenarios/catalog.json');

  const rows = useMemo(() => {
    if (!results.data || !users.data || !catalog.data) return [];
    const userById = Object.fromEntries(users.data.map((u) => [u.id, u]));
    const scenarioById = Object.fromEntries(catalog.data.map((s) => [s.id, s]));
    const scope = user.role === 'student' ? results.data.filter((r) => r.user_id === user.id) : results.data;
    return scope
      .map((r) => ({
        ...r,
        person: userById[r.user_id],
        scenario: scenarioById[r.scenario_id],
      }))
      .sort((a, b) => (a.date < b.date ? 1 : -1));
  }, [results.data, users.data, catalog.data, user]);

  const summary = useMemo(() => {
    if (!rows.length) return null;
    const avg = Math.round((rows.reduce((s, r) => s + r.score, 0) / rows.length) * 10) / 10;
    return {
      count: rows.length,
      avg,
      best: Math.max(...rows.map((r) => r.score)),
    };
  }, [rows]);

  if (results.loading || users.loading || catalog.loading) {
    return (
      <div className="app-shell">
        <AppHeader />
        <LoadingSpinner />
      </div>
    );
  }
  if (results.error || users.error || catalog.error) {
    return (
      <div className="app-shell">
        <AppHeader />
        <ErrorBanner message={results.error ?? users.error ?? catalog.error} />
      </div>
    );
  }

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="dds-back">
            <Link to="/">← Главная</Link>
          </div>
          <PageTitle
            title="Журнал успеваемости"
            subtitle={user.role === 'student' ? 'Ваши тренировки' : 'Тренировки всех пользователей'}
          />

          {summary && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{summary.count}</div>
                <div className="stat-label">Тренировок</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{summary.avg}%</div>
                <div className="stat-label">Средний балл</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{summary.best}%</div>
                <div className="stat-label">Лучший результат</div>
              </div>
            </div>
          )}

          {rows.length === 0 ? (
            <p className="catalog-empty">Данных о тренировках пока нет.</p>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Пользователь</th>
                    <th>Сценарий</th>
                    <th>Категория</th>
                    <th>Балл</th>
                    <th>Оценка</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.session_id}>
                      <td>{new Date(r.date).toLocaleDateString('ru-RU')}</td>
                      <td>{r.person?.name ?? r.user_id}</td>
                      <td>{r.scenario?.title ?? r.scenario_id}</td>
                      <td>
                        <span className="badge badge-cat tone-neutral">{categoryLabel(r.scenario?.category)}</span>
                      </td>
                      <td>{formatScore(r.score)}</td>
                      <td>
                        <span className={`verdict-mini ${VERDICT_TONES[r.verdict] ?? 'v-bad'}`}>
                          {r.verdict}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}