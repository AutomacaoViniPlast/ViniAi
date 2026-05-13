export type SessionUser = {
  id: number;
  nome: string;
  email: string;
  setor: string;
  nivel_acesso?: string;
  force_password_change?: boolean;
  photo?: string;
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

export function saveUserPhoto(userId: number, photo: string | null) {
  const key = `user_photo_${userId}`;
  if (photo) {
    localStorage.setItem(key, photo);
  } else {
    localStorage.removeItem(key);
  }
}

export function getUser(): SessionUser | null {
  const raw = localStorage.getItem("user");
  if (!raw) return null;

  try {
    const user = JSON.parse(raw) as SessionUser;
    if (user.id) {
      const savedPhoto = localStorage.getItem(`user_photo_${user.id}`);
      if (savedPhoto) user.photo = savedPhoto;
    }
    return user;
  } catch {
    return null;
  }
}

export function isUserStored(): boolean {
  return !!getUser();
}

export function isTokenValid(): boolean {
  const token = localStorage.getItem("token");
  if (!token) return false;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload.exp === "number" && payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}
