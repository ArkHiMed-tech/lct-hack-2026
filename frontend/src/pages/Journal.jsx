import { useMemo, useState } from 'react';
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

  // Поиск 112 (по инструкции): по умолчанию + расширенный по параметрам + фильтры.
  const [q, setQ] = useState('');
  const [advOpen, setAdvOpen] = useState(false);
  const [fWhat, setFWhat] = useState('');
  const [fStatus, setFStatus] = useState('');
  const [fChannel, setFChannel] = useState('');
  const [fNum, setFNum] = useState('');
  const [fOnly, setFOnly] = useState(''); // пустые карточки | Новые СМС | связи
  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter((r) => {
      const hay = `${r.scenario?.title ?? ''} ${r.person?.name ?? ''} ${r.scenario_id} ${r.date}`.toLowerCase();
      if (needle && !hay.includes(needle)) return false;
      if (fWhat && !(r.scenario?.title ?? '').toLowerCase().includes(fWhat.toLowerCase())) return false;
      if (fNum && !String(r.scenario_id).includes(fNum)) return false;
      if (fStatus && String(r.verdict) !== fStatus) return false;
      // fChannel / fOnly — моки тренажера (поля витрины), не режут выдачу
      void fChannel; void fOnly;
      return true;
    });
  }, [rows, q, fWhat, fStatus, fNum, fChannel, fOnly]);
  const resetFilters = () => { setQ(''); setFWhat(''); setFStatus(''); setFChannel(''); setFNum(''); setFOnly(''); };

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
            <Link to="/">← К списку происшествий</Link>
          </div>
          <PageTitle
            title="Журнал успеваемости"
            subtitle={user.role === 'student' ? 'Ваши тренировки' : 'Тренировки всех пользователей'}
          />

          {summary && (
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">{filtered.length}/{summary.count}</div>
                <div className="stat-label">Показано / тренировок</div>
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

          {/* Поиск по умолчанию (Журнал 112) */}
          <div className="dds-search">
            <div className="dds-search-main">
              <h1><span>Журнал</span><span className="dds-loupe">⌕</span></h1>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="поиск: что случилось, заявитель (ФИО/АОН), адрес, номер карточки" style={{ flex: 1, padding: '6px 10px' }} />
                <button type="button" className="btn-reset" onClick={() => setQ('')} title="Очистка обнуляет текст, результат остается">✕</button>
                <button type="button" className="btn-reset" onClick={resetFilters}>сбросить</button>
                <button type="button" className="btn-reset" onClick={() => window.open(window.location.href, '_blank')} title="Новый поиск — новое окно">новый поиск</button>
                <button type="button" className="btn-reset" onClick={() => setAdvOpen((v) => !v)}>расширенный по параметрам</button>
              </div>
              {advOpen && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginTop: 8, fontSize: 12 }}>
                  <label>Что случилось:<input value={fWhat} onChange={(e) => setFWhat(e.target.value)} /></label>
                  <label>Статус:<select value={fStatus} onChange={(e) => setFStatus(e.target.value)}><option value="">—</option><option value="excellent">excellent</option><option value="pass">pass</option><option value="fail">fail</option></select></label>
                  <label>Номер карточки:<input value={fNum} onChange={(e) => setFNum(e.target.value)} /></label>
                  <label>Канал связи:<select value={fChannel} onChange={(e) => setFChannel(e.target.value)}><option value="">—</option><option>МТС</option><option>Билайн</option><option>Мегафон</option><option>Теле2</option></select></label>
                  <label>АРМ / Оператор:<input placeholder="мок" /></label>
                  <label>Служба / Адрес / Описание:<input placeholder="мок" /></label>
                  <label>Показать:<select value={fOnly} onChange={(e) => setFOnly(e.target.value)}><option value="">все</option><option value="empty">пустые карточки</option><option value="sms">Новые СМС</option><option value="links">связи</option></select></label>
                  <label>Дата/время заведения:<input type="date" /></label>
                </div>
              )}
            </div>
          </div>

          {filtered.length === 0 ? (
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
                  {filtered.map((r) => (
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