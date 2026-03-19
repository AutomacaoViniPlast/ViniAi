import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL;
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY);

export const salvarMensagem = async (
  role: "user" | "assistant",
  content: string,
  sessionId: string,
  setor: string
) => {
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return;

  await supabase.from("conversations").insert({
    session_id: sessionId,
    user_id: user.id,
    setor,
    role,
    content,
  });
};

export const carregarHistorico = async (sessionId: string) => {
  const { data, error } = await supabase
    .from("conversations")
    .select("role, content, created_at")
    .eq("session_id", sessionId)
    .order("created_at", { ascending: true })
    .limit(50);

  if (error) { console.error("Erro ao carregar histórico:", error); return []; }
  return data as { role: "user" | "assistant"; content: string; created_at: string }[];
};