import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import useJson from '../hooks/useJson';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';

export default function Home() {
  const { user } = useAuth();
  const results = useJson('/data/results.json');
  const catalog = useJson('/data/scenarios/catalog.json');

  const stats = useMemo(() => {
    if (!results.data) return null;
    const mine = results.data.filter((r) => r.user_id === user.id);
    if (!mine.length) return null;
    const avg = Math.round((mine.reduce((s, r) => s + r.score, 0) / mine.length) * 10) / 10;
    return { count: mine.length, avg, best: Math.max(...mine.map((r) => r.score)) };
  }, [results.data, user.id]);

  if (results.loading || catalog.loading) {
    return (
      <div className="app-shell">
        <AppHeader />
        <LoadingSpinner />
      </div>
    );
  }
  if (results.error || catalog.error) {
    return (
      <div className="app-shell">
        <AppHeader />
        <ErrorBanner message={results.error ?? catalog.error} />
      </div>
    );
  }

  const firstName = user.name.split(' ')[0];
  const total = catalog.data?.length ?? 0;

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="dds-search">
            <div className="dds-search-main">
              <h1>Главная</h1>
              <div className="dds-search-sub">
                Здравствуйте, {firstName}! Учебный стенд диспетчера Системы 112
              </div>
            </div>
          </div>

          <div className="dds-list-head">
            <h2>Рабочее место ∧</h2>
          </div>

          {stats && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{stats.count}</div>
                <div className="stat-label">Выполнено тренировок</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.avg}%</div>
                <div className="stat-label">Средний балл</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.best}%</div>
                <div className="stat-label">Лучший результат</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{total}</div>
                <div className="stat-label">Сценариев доступно</div>
              </div>
            </div>
          )}

          <nav className="dds-tiles">
            <Link to="/card" className="dds-tile">
              <span className="dds-tile-ico">▤</span>
              <span className="dds-tile-title">Создание карточек</span>
              <span className="dds-tile-sub">Что случилось → ТЭГи → службы, как в АРМ</span>
            </Link>
            <Link to="/" className="dds-tile">
              <span className="dds-tile-ico">⌕</span>
              <span className="dds-tile-title">Поиск происшествий</span>
              <span className="dds-tile-sub">Список происшествий · {total} сценариев для отработки</span>
            </Link>
            <Link to="/journal" className="dds-tile">
              <span className="dds-tile-ico">☰</span>
              <span className="dds-tile-title">Журнал успеваемости</span>
              <span className="dds-tile-sub">Результаты тренировок и оценки по протоколу</span>
            </Link>
            {user.role === 'admin' && (
              <Link to="/admin" className="dds-tile">
                <span className="dds-tile-ico">⚙</span>
                <span className="dds-tile-title">Администрирование</span>
                <span className="dds-tile-sub">Пользователи, сценарии, рубрики проверки</span>
              </Link>
            )}
          </nav>

          {!stats && (
            <p className="catalog-empty">Тренировок ещё не было — начните со списка происшествий.</p>
          )}
        </main>
      </div>
    </div>
  );
}
