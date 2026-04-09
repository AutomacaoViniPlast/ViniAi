import { apiFetch } from "../lib/api";

export interface ApiConversation {
  id: string;
  titulo: string;
  pinned: boolean;
  criado_em: string;
  atualizado_em: string;
  ultima_mensagem?: string;
}

export interface ApiMessage {
  id: string;
  role: "user" | "assistant";
  conteudo: string;
  criado_em: string;
}

export async function listConversations(): Promise<ApiConversation[]> {
  const data = await apiFetch<{ conversations: ApiConversation[] }>("/conversations");
  return data.conversations;
}

export async function createConversation(titulo?: string): Promise<ApiConversation> {
  const data = await apiFetch<{ conversation: ApiConversation }>("/conversations", {
    method: "POST",
    body: JSON.stringify({ titulo: titulo || "Nova conversa" }),
  });
  return data.conversation;
}

export async function updateTitle(id: string, titulo: string): Promise<void> {
  await apiFetch(`/conversations/${id}/title`, {
    method: "PATCH",
    body: JSON.stringify({ titulo }),
  });
}

export async function togglePin(id: string): Promise<ApiConversation> {
  const data = await apiFetch<{ conversation: ApiConversation }>(`/conversations/${id}/pin`, {
    method: "PATCH",
  });
  return data.conversation;
}

export async function deleteConversation(id: string): Promise<void> {
  await apiFetch(`/conversations/${id}`, { method: "DELETE" });
}

export async function getMessages(conversationId: string): Promise<ApiMessage[]> {
  const data = await apiFetch<{ messages: ApiMessage[] }>(`/conversations/${conversationId}/messages`);
  return data.messages;
}

export async function saveMessage(
  conversationId: string,
  role: "user" | "assistant",
  conteudo: string
): Promise<ApiMessage> {
  const data = await apiFetch<{ message: ApiMessage }>(`/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ role, conteudo }),
  });
  return data.message;
}
