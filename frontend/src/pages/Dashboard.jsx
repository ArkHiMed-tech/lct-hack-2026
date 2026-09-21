import { Fragment, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import useJson from '../hooks/useJson';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';

function incidentNo(index) {
  return 36814844 + index;
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const scenarios = useJson('/api/scenarios');
  const results = useJson('/api/results');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const perPage = 10;

  const rows = useMemo(() => {
    if (!scenarios.data) return [];
    const q = query.trim().toLowerCase();
    let list = scenarios.data.map((s, i) => ({
      ...s,
      num: incidentNo(i),
      date: '17.09.26',
      time: `11:${String(11 + i).padStart(2, '0')}:0${i % 10}`,
      addr: s.id === 'scn-001' || i === 1 ? 'Москва , (ТАО, Вороновское) , Троицкий административный округ' : 'Нет',
      desc: s.summary,
    }));
    if (q) list = list.filter((r) => `${r.title} ${r.num} ${r.summary}`.toLowerCase().includes(q));
    return list;
  }, [scenarios.data, query]);

  const totalPages = Math.max(1, Math.ceil(rows.length / perPage));
  const pageRows = rows.slice((page - 1) * perPage, page * perPage);

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

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="dds-back">
            <Link to="/">← Главная</Link>
          </div>
          <div className="dds-search">
            <div className="dds-search-main">
              <h1>
                Поиск происшествий
                <span className="dds-loupe">⌕</span>
              </h1>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="dds-search-sub">расширенный по параметрам ⌄</span>
                <span style={{ display: 'flex', gap: 8 }}>
                  <input
                    value={query}
                    onChange={(e) => { setQuery(e.target.value); setPage(1); }}
                    placeholder="номер / тип / адрес"
                    style={{ fontSize: 12, padding: '3px 8px', border: '1px solid #999' }}
                  />
                  <button type="button" className="btn-reset" onClick={() => setQuery('')}>
                    сбросить
                  </button>
                </span>
              </div>
            </div>
          </div>

          <div className="dds-list-head">
            <h2>Список происшествий ∧</h2>
            <div className="dds-list-tools">
              <span>ⓘ уведомления</span>
              <select className="dds-select" defaultValue="">
                <option value="">выберите что показать</option>
                <option value="all">все происшествия</option>
                <option value="mine">мои тренировки</option>
              </select>
            </div>
          </div>

          <table className="dds-table">
            <thead>
              <tr>
                <th>⌄</th><th>Связи</th><th>ЧС</th><th>Опер.</th><th>АРМ</th><th>Номер</th>
                <th>Дата ↓</th><th>Время</th><th>Тип происшествия</th><th>Постр.</th>
                <th>Адрес</th><th>Статус службы</th><th />
              </tr>
            </thead>
            <tbody>
              {pageRows.map((r) => (
                <Fragment key={r.id}>                  <tr key={r.id} className="dds-row" onClick={() => navigate(`/scenario/${r.id}`)}>
                    <td>⌄</td>
                    <td>▐</td>
                    <td>⚡ 🕐</td>
                    <td className="dds-op">0</td>
                    <td>4</td>
                    <td>{r.num}</td>
                    <td>{r.date}</td>
                    <td className="dds-time">{r.time}</td>
                    <td className="wrap"><b>{r.title}</b></td>
                    <td>Нет</td>
                    <td className="dds-addr wrap">{r.addr}</td>
                    <td className="dds-status">🔕 Добавлена</td>
                    <td>🗎</td>
                  </tr>
                  <tr key={`${r.id}-d`} className="dds-desc">
                    <td colSpan={13}>
                      Описание: &nbsp; 17.09.2026 {r.time.slice(0, 5)}:{String(r.num).slice(-2)} УМЦ О. п. - <b>{r.title}</b>
                    </td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </table>

          <div className="dds-pager">
            <span>Страница: {page}</span>
            <span>Записей на странице: {perPage}</span>
            <span>{rows.length ? `1-${pageRows.length} из ${rows.length}` : '0 из 0'}</span>
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))}>‹</button>
            <button type="button" onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>›</button>
          </div>
        </main>
      </div>
    </div>
  );
}
