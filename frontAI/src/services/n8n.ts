import { supabase } from "./supabase";

export const sendChatMessage = async (message: string, setor: string = "GERAL") => {
  const WEBHOOK_URL = "https://tales1045.app.n8n.cloud/webhook/a1ff2a69-7b62-461c-b19d-9c58d01a8643/chat";

  const { data: { user } } = await supabase.auth.getUser();

  const sessionId = user
    ? `${user.id}_${setor.replace(/\s/g, "_")}`
    : `anonimo_${setor}`;

  const { data: profile } = await supabase
    .from("profiles")
    .select("nome")
    .eq("id", user?.id)
    .single();

  const response = await fetch(WEBHOOK_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chatInput: message,
      sessionId,
      userId: user?.id,
      userEmail: user?.email,
      userName: profile?.nome || "Usuário Desconhecido",
      setor,
    }),
  });

  if (!response.ok) throw new Error("Erro ao falar com a Viniplast");

  return await response.json();
};