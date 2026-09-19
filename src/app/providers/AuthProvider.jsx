import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi, setToken, isAuthenticated } from "../../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // Only "loading" if there's a stored token to verify; otherwise we already know.
  const [loading, setLoading] = useState(() => isAuthenticated());

  useEffect(() => {
    if (!isAuthenticated()) return;
    authApi
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  // The API client fires this when any protected call returns 401 (expired token).
  useEffect(() => {
    const onUnauthorized = () => setUser(null);
    window.addEventListener("somastar:unauthorized", onUnauthorized);
    return () => window.removeEventListener("somastar:unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await authApi.login({ email, password });
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const register = useCallback(async (name, email, password) => {
    const data = await authApi.register({ name, email, password });
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
