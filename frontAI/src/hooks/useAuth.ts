import { useEffect, useMemo, useState } from "react";
import { getToken, getUser, type SessionUser } from "../lib/storage";
import { getMe, signIn, signOut, signUp } from "../services/auth";

export function useAuth() {
  const [user, setUser] = useState<SessionUser | null>(getUser());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadSession() {
      const token = getToken();

      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const response = await getMe();
        setUser(response.user);
      } catch {
        signOut();
        setUser(null);
      } finally {
        setLoading(false);
      }
    }

    loadSession();
  }, []);

  async function login(email: string, password: string) {
    const response = await signIn(email, password);
    setUser(response.user);
    return response;
  }

  async function register(nome: string, email: string, password: string) {
    const response = await signUp(email, password, nome);
    setUser(response.user);
    return response;
  }

  function logout() {
    signOut();
    setUser(null);
  }

  return useMemo(
    () => ({
      user,
      loading,
      isAuthenticated: !!user,
      login,
      register,
      logout,
    }),
    [user, loading]
  );
}