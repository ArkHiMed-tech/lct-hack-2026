import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import useJson from '../hooks/useJson';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import PageTitle from '../components/PageTitle';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import ScenarioCard from '../components/ScenarioCard';
import { CATEGORIES } from '../lib/meta';

function StatCard({ label, value, hint }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

function computeStats(results, userId) {
  const mine = results.filter((r) => r.user_id === userId);
  if (mine.length === 0) return null;
  const avg = Math.round((mine.reduce((sum, r) => sum + r.score, 0) / mine.length) * 10) / 10;
  const last = mine[mine.length - 1];
  const best = Math.max(...mine.map((r) => r.score));
  return { count: mine.length, avg, last, best };
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const scenarios = useJson('/data/scenarios/catalog.json');
  const results = useJson('/data/results.json');
  const [filter, setFilter] = useState('all');

  const stats = useMemo(
    () => (results.data ? computeStats(results.data, user.id) : null),
    [results.data, user.id],
  );

  const categories = useMemo(() => ['all', ...Object.keys(CATEGORIES)], []);

  const visibleScenarios = useMemo(() => {
    if (!scenarios.data) return [];
    return filter === 'all'
      ? scenarios.data
      : scenarios.data.filter((s) => s.category === filter);
  }, [scenarios.data, filter]);

  const handleStart = (scenario) => {
    navigate(`/scenario/${scenario.id}`);
  };

  if (scenarios.loading || results.loading) {
    return (
      <div className="app-shell">
        <AppHeader />
        <LoadingSpinner />
      </div>
    );
  }
  if (scenarios.error || results.error) {
    return (
      <div className="app-shell">
        <AppHeader />
        <ErrorBanner message={scenarios.error ?? results.error} />
      </div>
    );
  }

  const firstName = user.name.split(' ')[0];

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <PageTitle
            title={`Здравствуйте, ${firstName}!`}
            subtitle="Выберите тренировку для отработки регламента приёма вызовов"
          />

          <section className="stats-grid">
            {stats ? (
              <>
                <StatCard label="Выполнено тренировок" value={stats.count} />
                <StatCard label="Средний балл" value={`${stats.avg}%`} />
                <StatCard label="Лучший результат" value={`${stats.best}%`} />
                <StatCard
                  label="Последняя тренировка"
                  value={stats.last.verdict === 'excellent' ? 'Отлично' : stats.last.verdict === 'pass' ? 'Зачтено' : 'Не зачтено'}
                  hint={`${new Date(stats.last.date).toLocaleDateString('ru-RU')} · ${stats.last.score}%`}
                />
              </>
            ) : (
              <div className="stats-empty">
                Тренировок ещё не было — начните с первого сценария.
              </div>
            )}
          </section>

          <section className="catalog">
            <div className="catalog-head">
              <h2>Каталог тренировок</h2>
              <div className="filter-bar">
                {categories.map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    className={`filter-chip ${filter === cat ? 'active' : ''}`}
                    onClick={() => setFilter(cat)}
                  >
                    {cat === 'all' ? 'Все' : CATEGORIES[cat].label}
                  </button>
                ))}
              </div>
            </div>

            {visibleScenarios.length === 0 ? (
              <p className="catalog-empty">Сценариев этой категории пока нет.</p>
            ) : (
              <div className="scenario-grid">
                {visibleScenarios.map((s) => (
                  <ScenarioCard key={s.id} scenario={s} onStart={handleStart} />
                ))}
              </div>
            )}
          </section>
        </main>
      </div>
    </div>
  );
}