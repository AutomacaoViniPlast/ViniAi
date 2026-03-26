export type SessionUser = {
  id: number;
  nome: string;
  email: string;
  setor: string;
  nivel_acesso?: string;
};

export type SessionData = {
  token: string;
  user: SessionUser;
};

export function saveSession(session: SessionData) {
  localStorage.setItem("token", session.token);
  localStorage.setItem("user", JSON.stringify(session.user));
}

export function clearSession() {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}

export function getToken() {
  return localStorage.getItem("token");
}

export function getUser(): SessionUser | null {
  const raw = localStorage.getItem("user");
  if (!raw) return null;

  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}