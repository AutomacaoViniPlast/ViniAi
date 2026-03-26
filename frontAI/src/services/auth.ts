import { apiFetch } from "../lib/api";
import { clearSession, saveSession, type SessionData } from "../lib/storage";

export async function signIn(email: string, password: string) {
  const data = await apiFetch<SessionData>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });

  saveSession(data);
  return data;
}

export async function signUp(email: string, password: string, nome: string) {
  const data = await apiFetch<SessionData>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ nome, email, password }),
  });

  saveSession(data);
  return data;
}

export async function getMe() {
  return apiFetch<{ user: SessionData["user"] }>("/auth/me", {
    method: "GET",
  });
}

export function signOut() {
  clearSession();
}