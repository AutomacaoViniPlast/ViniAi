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
  user: SessionUser;
};

export function saveSession(session: SessionData) {
  localStorage.setItem("user", JSON.stringify(session.user));
}

export function clearSession() {
  localStorage.removeItem("user");
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
