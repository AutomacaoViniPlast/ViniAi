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

export async function requestPasswordReset(email: string) {
  return apiFetch<{ message: string }>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(token: string, password: string) {
  return apiFetch<{ message: string }>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, password }),
  });
}

export async function changePassword(new_password: string, current_password?: string) {
  const data = await apiFetch<SessionData>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ new_password, current_password }),
  });
  saveSession(data);
  return data;
}

export function signOut() {
  clearSession();
}