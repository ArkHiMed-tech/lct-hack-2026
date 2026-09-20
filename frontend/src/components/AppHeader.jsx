import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ROLE_LABELS } from '../lib/meta';

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

const DAYS = ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'];
const MONTHS = [
  'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
  'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь',
];

export default function AppHeader({ title = 'ГБУ Система 112' }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const now = useClock();
  const pad = (n) => String(n).padStart(2, '0');
  const dateStr = `${DAYS[now.getDay()]}, ${now.getDate()} ${MONTHS[now.getMonth()]} ${now.getFullYear()}`;

  return (
    <header className="app-header">
      <div className="brand">
        <div className="brand-text">
          <strong>{title}</strong>
        </div>
      </div>
      <div className="header-right">
        <div className="dds-clock">
          <div className="dds-user">
            <span className="d">{dateStr}</span>
            <span className="u">
              {user ? `, ${user.name.split(' ')[0]} ${user.name.split(' ')[1]?.[0] ?? ''}. · ${user.post ?? ROLE_LABELS[user.role] ?? user.role}` : ''}
              {'  '}◉ ⚙ ✎ ⚑
              <button type="button" className="header-logout" onClick={() => { logout(); navigate('/login'); }}>
                Выйти
              </button>
            </span>
          </div>
          <div className="t">
            {pad(now.getHours())}:{pad(now.getMinutes())}
            <span style={{ fontSize: 14, verticalAlign: 'top' }}>:{pad(now.getSeconds())}</span>
          </div>
        </div>
      </div>
    </header>
  );
}
