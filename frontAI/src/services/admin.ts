import { apiFetch } from "../lib/api";

export interface AdminUser {
  id: number;
  nome: string;
  email: string;
  setor: string;
  nivel_acesso: string;
  ativo: boolean;
  force_password_change?: boolean;
}

export async function listUsers(): Promise<AdminUser[]> {
  return apiFetch<AdminUser[]>("/admin/users");
}

export async function createUser(data: {
  nome: string;
  email: string;
  password: string;
  setor: string;
  nivel_acesso: string;
  force_password_change?: boolean;
}): Promise<AdminUser> {
  return apiFetch<AdminUser>("/admin/users", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateUser(
  id: number,
  data: Partial<{ nome: string; setor: string; nivel_acesso: string; ativo: boolean; password: string; force_password_change: boolean }>
): Promise<AdminUser> {
  return apiFetch<AdminUser>(`/admin/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}
