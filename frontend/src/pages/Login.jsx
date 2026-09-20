import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useJson from '../hooks/useJson';
import { useAuth } from '../context/AuthContext';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';

function CityArt() {
  return (
    <div className="login-city" aria-hidden>
      <svg viewBox="0 0 1200 500" preserveAspectRatio="xMidYMax slice">
        <g fill="#ffffff" opacity="0.85">
          <rect x="40" y="300" width="120" height="200" />
          <rect x="180" y="340" width="140" height="160" />
          <rect x="340" y="280" width="90" height="220" />
          <rect x="450" y="200" width="70" height="300" />
          <rect x="540" y="230" width="70" height="270" />
          <rect x="760" y="330" width="80" height="170" />
          <rect x="850" y="290" width="150" height="210" />
          <rect x="1020" y="350" width="130" height="150" />
        </g>
        <g fill="#9cc3de">
          <rect x="0" y="60" width="90" height="440" />
          <rect x="110" y="20" width="90" height="480" />
          <rect x="220" y="90" width="70" height="410" />
          <rect x="310" y="150" width="90" height="350" />
          <rect x="420" y="170" width="80" height="330" />
          <rect x="520" y="140" width="90" height="360" />
          <rect x="660" y="270" width="60" height="230" />
        </g>
        <g fill="#7b7b7b" opacity="0.35">
          {Array.from({ length: 8 }).map((_, r) =>
            Array.from({ length: 4 }).map((_, c) => (
              <rect key={`${r}-${c}`} x={52 + c * 28} y={320 + r * 20} width={90} height={8} />
            )),
          )}
        </g>
      </svg>
    </div>
  );
}

export default function Login() {
  const navigate = useNavigate();
  const { user, login } = useAuth();
  const users = useJson('/data/users.json');
  const roles = useJson('/data/roles.json');
  const [loginName, setLoginName] = useState('');
  const [password, setPassword] = useState('');
  const [roleId, setRoleId] = useState('student');
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  const handleSubmit = (evt) => {
    evt.preventDefault();
    setError('');
    const list = users.data ?? [];
    const active = list.filter((u) => u.active);
    let person = null;
    const q = loginName.trim().toLowerCase();
    if (q) {
      person =
        active.find((u) => u.id.toLowerCase() === q) ??
        active.find((u) => u.name.toLowerCase().includes(q)) ??
        null;
    }
    if (!person) person = active[0];
    if (!person) {
      setError('Нет доступных пользователей');
      return;
    }
    login({ ...person, role: roleId });
    navigate('/', { replace: true });
  };

  if (users.loading || roles.loading) return <LoadingSpinner label="Загрузка…" />;
  if (users.error || roles.error) {
    return (
      <div className="login-page">
        <ErrorBanner message={users.error ?? roles.error} />
      </div>
    );
  }

  return (
    <div className="login-page">
      <CityArt />
      <div className="login-inner">
        <div className="login-left" />
        <div className="login-right">
          <h1>
            112 <small>ВХОД В СИСТЕМУ</small>
          </h1>
          <form onSubmit={handleSubmit}>
            <label className="field">
              <span>логин:</span>
              <input
                value={loginName}
                onChange={(e) => setLoginName(e.target.value)}
                placeholder="umc_operdds1"
              />
            </label>
            <label className="field">
              <span>пароль:</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <label className="field">
              <span>роль (учебный режим):</span>
              <select value={roleId} onChange={(e) => setRoleId(e.target.value)}>
                {(roles.data ?? []).map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.title}
                  </option>
                ))}
              </select>
            </label>
            {error && <p className="form-error">{error}</p>}
            <button type="submit" className="btn-login">
              ВОЙТИ
            </button>
          </form>
          <div className="login-support">
            Техподдержка
            <br />
            +7 (495) 197-89-81
            <br />
            (многоканальный)
            <br />
            <a href="mailto:hd-112@mos.ru">hd-112@mos.ru</a>
          </div>
          <p className="login-footnote">Учебный стенд. Логин можно ввести свободный — подберём первого активного пользователя.</p>
        </div>
      </div>
    </div>
  );
}
