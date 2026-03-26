type StoredUser = {
  id?: number;
  nome?: string;
  email?: string;
  setor?: string;
};

export const sendChatMessage = async (
  message: string,
  setor: string = "GERAL",
  sessionId?: string
) => {
  const WEBHOOK_URL =
    import.meta.env.VITE_N8N_WEBHOOK_URL || "";

  if (!WEBHOOK_URL) {
    throw new Error("Webhook do n8n não configurado.");
  }

  const rawUser = localStorage.getItem("user");

  let user: StoredUser = {};

  if (rawUser) {
    try {
      user = JSON.parse(rawUser) as StoredUser;
    } catch {
      user = {};
    }
  }

  const finalSetor = user.setor || setor || "GERAL";

  const finalSessionId =
    sessionId ||
    (user.id
      ? `${user.id}_${finalSetor.replace(/\s/g, "_")}`
      : `sessao_${finalSetor.replace(/\s/g, "_")}_${Date.now()}`);

  const response = await fetch(WEBHOOK_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      chatInput: message,
      sessionId: finalSessionId,
      userId: user.id ?? null,
      userEmail: user.email ?? null,
      userName: user.nome ?? "Usuário",
      setor: finalSetor,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(errorText || "Erro ao falar com a ViniAI");
  }

  return await response.json();
};