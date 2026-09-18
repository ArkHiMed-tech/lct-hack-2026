import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ROLE_LABELS } from '../lib/meta';

export default function AppHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="app-header">
      <div className="brand">
        <img src="/favicon.svg" alt="" className="brand-logo" />
        <div className="brand-text">
          <strong>Симулятор диспетчера 112</strong>
          <span>Учебный центр экстренных служб</span>
        </div>
      </div>

      <div className="header-right">
        {user && (
          <>
            <div className="user-chip">
              <span className="user-chip-name">{user.name}</span>
              <span className="user-chip-role">{ROLE_LABELS[user.role] ?? user.role}</span>
            </div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={handleLogout}>
              Выйти
            </button>
          </>
        )}
      </div>
    </header>
  );
}