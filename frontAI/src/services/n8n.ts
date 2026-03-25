export const sendChatMessage = async (
  message: string,
  setor: string = "GERAL",
  sessionId?: string
) => {
  const WEBHOOK_URL = "";

  const finalSessionId =
    sessionId || `sessao_${setor.replace(/\s/g, "_")}_${Date.now()}`;

  const response = await fetch(WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chatInput: message,
      sessionId: finalSessionId,
      setor,
      userId: null,
      userEmail: null,
      userName: "Usuário Local",
    }),
  });

  if (!response.ok) {
    throw new Error("Erro ao falar com a Viniplast");
  }

  return await response.json();
};