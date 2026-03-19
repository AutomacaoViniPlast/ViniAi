import { useState, useEffect, useRef } from "react";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import EmptyState from "@/components/chat/EmptyState";
import { sendChatMessage } from "../services/n8n";

import abrir from "../image/abrir.png";
import fechar from "../image/fechar.png";
import { supabase } from "../services/supabase";
import { LogOut, Pin, Trash2 } from "lucide-react";

interface Message {
  id: string;
  content: string;
  role: "user" | "assistant";
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  pinned?: boolean;
}

interface UserProfile {
  nome: string;
  setor: string;
}

const generateId = () =>
  Math.random().toString(36).substring(2) + Date.now().toString(36);

const Index = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [search, setSearch] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [carregando, setCarregando] = useState(true);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const init = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { window.location.href = "/"; return; }

      const uid = session.user.id;
      setUserId(uid);

      const { data: profile } = await supabase
        .from("profiles")
        .select("nome, setor")
        .eq("id", uid)
        .single();

      if (profile) setUserProfile(profile);

      await carregarTodasConversas(uid);
      setCarregando(false);
    };
    init();
  }, []);

  const carregarTodasConversas = async (uid: string) => {
    const { data, error } = await supabase
      .from("conversations")
      .select("session_id, role, content, created_at")
      .eq("user_id", uid)
      .order("created_at", { ascending: true });

    if (error) { console.error("Erro ao carregar conversas:", error); return; }
    if (!data || data.length === 0) return;

    // Busca o pinned de cada conversa
    const { data: metaData } = await supabase
      .from("conversation_meta")
      .select("session_id, pinned")
      .eq("user_id", uid);

    const metaMap: Record<string, boolean> = {};
    metaData?.forEach((m) => { metaMap[m.session_id] = m.pinned; });

    const grupos: Record<string, typeof data> = {};
    data.forEach((row) => {
      if (!grupos[row.session_id]) grupos[row.session_id] = [];
      grupos[row.session_id].push(row);
    });

    const convs: Conversation[] = Object.entries(grupos).map(([sessionId, msgs]) => {
      const primeiraMsgUsuario = msgs.find((m) => m.role === "user");
      return {
        id: sessionId,
        title: primeiraMsgUsuario?.content.slice(0, 40) || "Nova conversa",
        messages: msgs.map((m) => ({
          id: generateId(),
          content: m.content,
          role: m.role as "user" | "assistant",
        })),
        createdAt: new Date(msgs[0].created_at).getTime(),
        pinned: metaMap[sessionId] || false,
      };
    });

    convs.sort((a, b) => b.createdAt - a.createdAt);
    setConversations(convs);
    setActiveId(convs[0]?.id || null);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeId, conversations, isTyping]);

  const activeConversation = conversations.find((c) => c.id === activeId);

  const handleLogout = async () => {
    try {
      await supabase.auth.signOut();
      sessionStorage.clear();
      window.location.href = "/";
    } catch (error) {
      console.error("Erro ao deslogar:", error);
      window.location.href = "/";
    }
  };

  const createNewConversation = () => {
    if (!userId) return;
    const sessionId = `${userId}_${Date.now()}`;

    // Registra o meta no banco
    supabase.from("conversation_meta").insert({
      session_id: sessionId,
      user_id: userId,
      pinned: false,
    });

    const newConv: Conversation = {
      id: sessionId,
      title: "Nova conversa",
      messages: [],
      createdAt: Date.now(),
      pinned: false,
    };
    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);
    setIsSidebarOpen(false);
  };

  const deleteConversation = async (id: string) => {
    await supabase.from("conversations").delete().eq("session_id", id);
    await supabase.from("conversation_meta").delete().eq("session_id", id);
    setConversations((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      if (id === activeId) setActiveId(updated[0]?.id || null);
      return updated;
    });
  };

  const togglePin = async (id: string) => {
    const conv = conversations.find((c) => c.id === id);
    if (!conv || !userId) return;

    const newPinned = !conv.pinned;

    // Upsert: cria ou atualiza
    await supabase.from("conversation_meta").upsert({
      session_id: id,
      user_id: userId,
      pinned: newPinned,
    });

    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, pinned: newPinned } : c))
    );
  };

  const handleSend = async (content: string) => {
    if (!activeConversation || !userId) return;

    const sessionId = activeConversation.id;
    const setor = userProfile?.setor || "GERAL";
    const userName = userProfile?.nome || "Desconhecido";

    const userMessage: Message = { id: generateId(), content, role: "user" };
    setConversations((prev) =>
      prev.map((c) =>
        c.id === sessionId
          ? {
            ...c,
            title: c.messages.length === 0 ? content.slice(0, 40) : c.title,
            messages: [...c.messages, userMessage],
          }
          : c
      )
    );

    await supabase.from("conversations").insert({
      session_id: sessionId,
      user_id: userId,
      setor,
      user_name: userName,
      user_setor: setor,
      role: "user",
      content,
    });

    setIsTyping(true);

    try {
      const data = await sendChatMessage(content, setor);

      if (typeof data === "object" && data.action === "REDIRECIONAR") {
        const redirectMsg: Message = {
          id: generateId(),
          content: data.output || "Redirecionando para atendimento humano...",
          role: "assistant",
        };
        setConversations((prev) =>
          prev.map((c) =>
            c.id === sessionId ? { ...c, messages: [...c.messages, redirectMsg] } : c
          )
        );
        await supabase.from("conversations").insert({
          session_id: sessionId,
          user_id: userId,
          setor,
          user_name: userName,
          user_setor: setor,
          role: "assistant",
          content: redirectMsg.content,
        });
        window.open("https://wa.me/5511963984612", "_blank");
        return;
      }

      const responseText =
        data?.message ||
        data?.output ||
        data?.response ||
        (typeof data === "string" ? data : "Sem resposta.");

      const assistantMessage: Message = {
        id: generateId(),
        content: responseText,
        role: "assistant",
      };
      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? { ...c, messages: [...c.messages, assistantMessage] }
            : c
        )
      );

      await supabase.from("conversations").insert({
        session_id: sessionId,
        user_id: userId,
        setor,
        user_name: userName,
        user_setor: setor,
        role: "assistant",
        content: responseText,
      });
    } catch (error) {
      console.error(error);
      const errMsg: Message = {
        id: generateId(),
        content: "Desculpe, tive um problema de conexão.",
        role: "assistant",
      };
      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId ? { ...c, messages: [...c.messages, errMsg] } : c
        )
      );
    } finally {
      setIsTyping(false);
    }
  };

  const filteredConversations = conversations
    .filter((c) => c.title.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (a.pinned && !b.pinned) return -1;
      if (!a.pinned && b.pinned) return 1;
      return b.createdAt - a.createdAt;
    });

  if (carregando) {
    return (
      <div className="flex h-screen bg-background text-white items-center justify-center">
        <p className="text-zinc-400 text-sm">Carregando conversas...</p>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-background text-white overflow-hidden">
      <aside
        className={`
          bg-zinc-950 border-r border-zinc-800 flex flex-col
          transition-all duration-500 ease-in-out
          md:relative
          ${isSidebarCollapsed ? "md:w-14" : "md:w-80"}
          fixed inset-y-0 left-0 z-40 w-80
          ${isSidebarOpen ? "translate-x-0" : "-translate-x-full"}
          md:translate-x-0
        `}
      >
        <div className="flex items-center justify-between p-4 border-b border-zinc-800">
          {!isSidebarCollapsed && (
            <div>
              <h1 className="text-base font-semibold">ViniAI</h1>
              {userProfile && (
                <p className="text-xs text-zinc-400 mt-0.5">
                  {userProfile.nome} · <span className="text-primary">{userProfile.setor}</span>
                </p>
              )}
            </div>
          )}
          <button
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            className="hidden md:block text-zinc-400 hover:text-white"
          >
            <img src={isSidebarCollapsed ? fechar : abrir} alt="Toggle Sidebar" className="w-5 h-5" />
          </button>
          <button onClick={() => setIsSidebarOpen(false)} className="md:hidden text-zinc-400">✕</button>
        </div>

        <div className="p-2">
          <button
            onClick={createNewConversation}
            className="bg-primary px-4 py-2 rounded-lg text-sm transition-all duration-300 w-full flex justify-center items-center gap-2"
          >
            {isSidebarCollapsed ? "+" : "+ Nova Conversa"}
          </button>
        </div>

        {!isSidebarCollapsed && (
          <div className="px-2 pb-3">
            <input
              type="text"
              placeholder="Buscar conversa..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-2 space-y-1">
          {filteredConversations.map((conv) => (
            <div
              key={conv.id}
              className={`group flex items-center justify-between px-3 py-2 rounded-lg text-sm transition ${activeId === conv.id ? "bg-zinc-800" : "hover:bg-zinc-900"
                }`}
            >
              <button
                onClick={() => { setActiveId(conv.id); setIsSidebarOpen(false); }}
                className={`text-left flex items-center gap-1 ${isSidebarCollapsed ? "w-full justify-center" : "flex-1 min-w-0"
                  }`}
              >
                {isSidebarCollapsed ? "💬" : (
                  <>
                    {conv.pinned && <Pin size={12} className="text-yellow-400 shrink-0" />}
                    <span className="truncate">{conv.title}</span>
                  </>
                )}
              </button>

              {!isSidebarCollapsed && (
                <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition ml-2">
                  <button onClick={() => togglePin(conv.id)} title="Fixar">
                    <Pin size={14} className={conv.pinned ? "text-primary" : "text-zinc-400"} />
                  </button>
                  <button onClick={() => deleteConversation(conv.id)} title="Excluir">
                    <Trash2 size={14} className="text-zinc-400 hover:text-red-400" />
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="p-2 border-t border-zinc-800 mt-auto bg-zinc-950">
          <button
            onClick={handleLogout}
            className={`
              flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-red-400
              hover:bg-red-950/30 transition-all duration-300 w-full
              ${isSidebarCollapsed ? "justify-center" : "justify-start"}
            `}
          >
            <LogOut size={18} />
            {!isSidebarCollapsed && <span>Sair da conta</span>}
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col min-w-0 min-h-0">
        <div className="md:hidden p-3 border-b border-zinc-800 shrink-0">
          <button onClick={() => setIsSidebarOpen(true)}>
            <img src={abrir} alt="Abrir Menu" className="w-6 h-6" />
          </button>
        </div>

        <div className="flex-1 flex flex-col min-h-0">
          {!activeConversation || activeConversation.messages.length === 0 ? (
            <EmptyState
              onSuggestionClick={handleSend}
              setor={userProfile?.setor}
            />
          ) : (
            <div className="flex-1 overflow-y-auto px-4 md:px-6 py-6 space-y-6">
              {activeConversation.messages.map((msg) => (
                <ChatMessage key={msg.id} id={msg.id} content={msg.content} role={msg.role} />
              ))}
              {isTyping && <ChatMessage id="typing" content="" role="assistant" isTyping />}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        <div className="p-4 border-t border-zinc-800 shrink-0">
          <ChatInput onSend={handleSend} disabled={!activeConversation || isTyping} />
        </div>
      </main>
    </div>
  );
};

export default Index;