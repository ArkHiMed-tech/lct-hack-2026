import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const { user, signIn } = useAuth();
  const [loginName, setLoginName] = useState('umc_operdds1');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (user) navigate('/', { replace: true });
  }, [user, navigate]);

  const handleSubmit = async (evt) => {
    evt.preventDefault();
    setError('');
    const err = await signIn(loginName, password);
    if (err) {
      setError(err);
      return;
    }
    navigate('/', { replace: true });
  };

  return (
    <div className="login-page">
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
                autoComplete="username"
              />
            </label>
            <label className="field">
              <span>пароль:</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
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
        </div>
      </div>
    </div>
  );
}
