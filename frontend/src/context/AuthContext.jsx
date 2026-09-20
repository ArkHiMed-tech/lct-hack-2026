import { createContext, useContext, useState } from 'react';
import { authenticate } from '../lib/accounts';

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

  // Возвращает null при успехе либо текст ошибки
  const signIn = (login, password) => {
    const res = authenticate(login, password);
    if (res.error) return res.error;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(res.user));
    } catch {
      /* ignore */
    }
    setUser(res.user);
    return null;
  };

  const logout = () => {
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
