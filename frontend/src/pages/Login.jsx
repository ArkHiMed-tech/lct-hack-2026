import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import useJson from '../hooks/useJson';
import { useAuth } from '../context/AuthContext';
import { ROLE_LABELS } from '../lib/meta';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';

export default function Login() {
  const navigate = useNavigate();
  const { user, login } = useAuth();

  const users = useJson('/data/users.json');
  const roles = useJson('/data/roles.json');

  const [userId, setUserId] = useState('');
  const [roleId, setRoleId] = useState('student');
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  const handleSubmit = (evt) => {
    evt.preventDefault();
    setError('');
    if (!user) {
      if (!userId) {
        setError('Выберите пользователя');
        return;
      }
      const person = users.data.find((u) => u.id === userId);
      if (!person) {
        setError('Пользователь не найден');
        return;
      }
      login({ ...person, role: roleId });
    }
    navigate('/', { replace: true });
  };

  if (users.loading || roles.loading) return <LoadingSpinner label="Загрузка справочников…" />;
  if (users.error || roles.error) {
    return (
      <div className="login-page">
        <ErrorBanner message={users.error ?? roles.error} />
      </div>
    );
  }

  const activeUsers = users.data.filter((u) => u.active);

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <img src="/favicon.svg" alt="" />
          <h1>Учебный симулятор диспетчера</h1>
          <p>Приём и обработка вызовов системы 112</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <label className="field">
            <span>Пользователь</span>
            <select value={userId} onChange={(e) => setUserId(e.target.value)}>
              <option value="">— выберите —</option>
              {activeUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                  {u.group ? ` (${u.group})` : ''}
                </option>
              ))}
            </select>
          </label>

          <label className="field">
            <span>Роль</span>
            <select value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              {roles.data.map((r) => (
                <option key={r.id} value={r.id}>
                  {ROLE_LABELS[r.id] ?? r.title}
                </option>
              ))}
            </select>
          </label>

          {error && <p className="form-error">{error}</p>}

          <button type="submit" className="btn btn-primary btn-block">
            Войти в систему
          </button>
        </form>

        <p className="login-footnote">
          Прототип. Данные приходят из <code>public/data/*.json</code>
        </p>
      </div>
    </div>
  );
}