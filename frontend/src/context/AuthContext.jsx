import { createContext, useContext, useEffect, useState } from 'react';

const STORAGE_KEY = 'sim112-user';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    let active = true;

    const restoreSession = async () => {
      try {
        const response = await fetch('/api/auth/me', { credentials: 'include' });
        if (!response.ok) {
          if (active) {
            localStorage.removeItem(STORAGE_KEY);
            setUser(null);
          }
          return;
        }

        const data = await response.json().catch(() => null);
        if (!data || !active) return;

        try {
          localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        } catch {
          /* ignore */
        }
        setUser(data);
      } catch {
        if (active) {
          localStorage.removeItem(STORAGE_KEY);
          setUser(null);
        }
      }
    };

    restoreSession();
    return () => {
      active = false;
    };
  }, []);

  // Возвращает null при успехе либо текст ошибки
  const signIn = async (login, password) => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ login, password }),
      });

      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        return data.detail || 'Ошибка входа';
      }

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      } catch {
        /* ignore */
      }
      setUser(data);
      return null;
    } catch {
      return 'Не удалось подключиться к серверу';
    }
  };

  const logout = async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      /* ignore */
    }

    localStorage.removeItem(STORAGE_KEY);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, signIn, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
