import { useState, useEffect, useRef } from "react";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import EmptyState from "@/components/chat/EmptyState";
import { sendChatMessage } from "../services/n8n";

import logo from "../image/logoviniai.png";
import abrir from "../image/abrir.png";
import fechar from "../image/fechar.png";
import { Pin, Trash2, LogOut, Plus, MessageSquare, Search, PanelLeftClose, PanelLeftOpen } from "lucide-react";

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
  const [isLogoHovered, setIsLogoHovered] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const rawUser = localStorage.getItem("user");

    let parsedUser: UserProfile = {
      nome: "Usuário",
      setor: "GERAL",
    };

    if (rawUser) {
      try {
        const user = JSON.parse(rawUser);
        parsedUser = {
          nome: user.nome || "Usuário",
          setor: user.setor || "GERAL",
        };
      } catch {
        parsedUser = {
          nome: "Usuário",
          setor: "GERAL",
        };
      }
    }

    setUserProfile(parsedUser);

    const novaConversa: Conversation = {
      id: generateId(),
      title: "Nova conversa",
      messages: [],
      createdAt: Date.now(),
      pinned: false,
    };

    setConversations([novaConversa]);
    setActiveId(novaConversa.id);
    setCarregando(false);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeId, conversations, isTyping]);

  const activeConversation = conversations.find((c) => c.id === activeId);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/auth";
  };

  const createNewConversation = () => {
    const newConv: Conversation = {
      id: generateId(),
      title: "Nova conversa",
      messages: [],
      createdAt: Date.now(),
      pinned: false,
    };

    setConversations((prev) => [newConv, ...prev]);
    setActiveId(newConv.id);
    setIsSidebarOpen(false);
  };

  const deleteConversation = (id: string) => {
    setConversations((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      if (id === activeId) setActiveId(updated[0]?.id || null);
      return updated;
    });
  };

  const togglePin = (id: string) => {
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, pinned: !c.pinned } : c))
    );
  };

  const handleSend = async (content: string) => {
    if (!activeConversation) return;

    const sessionId = activeConversation.id;
    const setor = userProfile?.setor || "GERAL";

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

    setIsTyping(true);

    try {
      const data = await sendChatMessage(content, setor, sessionId);

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

  /* ── Avatar iniciais do usuário ── */
  const initials = userProfile?.nome
    ? userProfile.nome.split(" ").map((n) => n[0]).slice(0, 2).join("").toUpperCase()
    : "U";

  if (carregando) {
    return (
      <div className="flex h-screen items-center justify-center" style={{ background: "hsl(220 30% 7%)" }}>
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-12 h-12 rounded-2xl flex items-center justify-center animate-pulse"
            style={{ background: "hsl(4 82% 47%)" }}
          >
            <span className="text-white font-bold text-sm">AI</span>
          </div>
          <p style={{ color: "hsl(215 15% 58%)", fontSize: "0.85rem" }}>Carregando...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#09090fff", color: "hsl(0 0% 95%)" }}>

      {/* ── Overlay mobile ── */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 z-30 md:hidden"
          style={{ background: "hsl(0 0% 0% / 0.5)" }}
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* ══════════════ SIDEBAR ══════════════ */}
      <aside
        style={{
          width: isSidebarCollapsed ? "60px" : "290px",
          background: "#08080eff",
          transition: "width 0.28s cubic-bezier(0.4,0,0.2,1)",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          position: "fixed" as const,
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 40,
          transform: isSidebarOpen || window.innerWidth >= 768 ? "translateX(0)" : "translateX(-100%)",
        }}
        className={`${isSidebarOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
      >
        {/* Sidebar header */}
        <div
          className="flex items-center justify-between p-3 shrink-0"
          style={{ borderBottom: "1px solid #23272fff", minHeight: "60px" }}
        >
          {/* Modo EXPANDIDO: logo + nome à esquerda, botão de recolher à direita */}
          {!isSidebarCollapsed && (
            <>
              <div className="flex items-center gap-2.5 overflow-hidden">
                <div
                  className="w-8 h-8 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: "#c52318ff" }}
                >
                  <img src={logo} alt="ViniAI Logo" className="w-[80%] h-[80%] object-contain" />
                </div>
                <div className="overflow-hidden">
                  <p className="font-semibold text-sm leading-tight truncate" style={{ color: "hsl(0 0% 95%)" }}>ViniAI</p>
                  <p className="text-xs truncate" style={{ color: "hsl(215 15% 58%)" }}>
                    {userProfile?.nome}
                    {userProfile?.setor && (
                      <span style={{ color: "hsl(4 82% 60%)" }}> · {userProfile.setor}</span>
                    )}
                  </p>
                </div>
              </div>
              {/* Botão de recolher — só aparece quando expandida */}
              <button
                onClick={() => setIsSidebarCollapsed(true)}
                className="hidden md:flex items-center justify-center w-7 h-7 rounded-full transition-all duration-200 shrink-0"
                style={{ color: "hsl(215 15% 58%)" }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = "hsl(220 20% 16%)";
                  e.currentTarget.style.color = "hsl(0 0% 95%)";
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "hsl(215 15% 58%)";
                }}
                title="Recolher"
              >
                <PanelLeftClose size={16} />
              </button>
              {/* Botão fechar mobile */}
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="md:hidden flex items-center justify-center w-7 h-7 rounded-full"
                style={{ color: "hsl(215 15% 58%)" }}
              >
                ✕
              </button>
            </>
          )}

          {/* Modo COLAPSADO: só o logo VI; no hover vira ícone de expandir */}
          {isSidebarCollapsed && (
            <button
              onClick={() => setIsSidebarCollapsed(false)}
              onMouseEnter={() => setIsLogoHovered(true)}
              onMouseLeave={() => setIsLogoHovered(false)}
              className="hidden md:flex mx-auto items-center justify-center w-8 h-8 rounded-xl transition-all duration-200"
              style={{
                background: isLogoHovered ? "hsl(220 20% 18%)" : "#b62015ff",
                color: "#fff",
              }}
              title="Expandir"
            >
              {isLogoHovered
                ? <PanelLeftOpen size={16} />
                : <img src={logo} alt="ViniAI Logo" className="w-[80%] h-[80%] object-contain" />
              }
            </button>
          )}
        </div>

        {/* Nova conversa */}
        <div className="p-2 pt-3 shrink-0">
          <button
            onClick={createNewConversation}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl text-sm font-medium transition-all duration-200"
            style={{
              background: "#b62015ff",
              color: "#fff",
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "hsl(4 82% 40%)";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 12px hsl(4 82% 47% / 0.4)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "hsl(4 82% 47%)";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
            }}
          >
            <Plus size={15} strokeWidth={2.5} />
            {!isSidebarCollapsed && <span>Nova Conversa</span>}
          </button>
        </div>

        {/* Search */}
        {!isSidebarCollapsed && (
          <div className="px-2 pb-2 shrink-0">
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-xl"
              style={{ background: "hsla(216, 33%, 6%, 1.00)", border: "1px solid hsl(220 15% 16%)" }}
            >
              <Search size={14} style={{ color: "hsl(215 15% 58%)", flexShrink: 0 }} />
              <input
                type="text"
                placeholder="Buscar conversa..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 bg-transparent text-sm outline-none"
                style={{
                  color: "hsl(0 0% 95%)",
                  caretColor: "hsl(4 82% 47%)",
                }}
              />
            </div>
          </div>
        )}

        {/* Lista de conversas */}
        <div className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5">
          {!isSidebarCollapsed && filteredConversations.length > 0 && (
            <p className="text-xs font-medium px-2 py-1.5" style={{ color: "hsl(215 15% 45%)" }}>
              Conversas
            </p>
          )}

          {filteredConversations.map((conv) => (
            <div
              key={conv.id}
              className="group relative flex items-center gap-1 px-2.5 py-2.5 rounded-xl text-sm transition-all duration-150 cursor-pointer"
              style={{
                background: activeId === conv.id ? "#0d111bff" : "transparent",
                color: activeId === conv.id ? "hsl(0 0% 95%)" : "hsl(215 15% 68%)",
              }}
              onMouseEnter={e => {
                if (activeId !== conv.id)
                  (e.currentTarget as HTMLDivElement).style.background = "hsl(220 20% 14%)";
              }}
              onMouseLeave={e => {
                if (activeId !== conv.id)
                  (e.currentTarget as HTMLDivElement).style.background = "transparent";
              }}
            >
              {isSidebarCollapsed ? (
                <button
                  onClick={() => { setActiveId(conv.id); setIsSidebarOpen(false); }}
                  className="w-full flex justify-center"
                  title={conv.title}
                >
                  <MessageSquare size={16} />
                </button>
              ) : (
                <>
                  <MessageSquare size={14} className="shrink-0 opacity-50" />
                  <button
                    onClick={() => { setActiveId(conv.id); setIsSidebarOpen(false); }}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="flex items-center gap-1 min-w-0">
                      {conv.pinned && <Pin size={10} style={{ color: "hsl(4 82% 60%)", flexShrink: 0 }} />}
                      <span className="truncate text-[13px]">{conv.title}</span>
                    </div>
                  </button>
                  {/* Ações hover */}
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); togglePin(conv.id); }}
                      className="p-1 rounded-xl transition-all duration-150"
                      style={{ color: conv.pinned ? "hsl(4 82% 60%)" : "hsl(215 15% 55%)" }}
                      onMouseEnter={e => (e.currentTarget.style.background = "hsl(220 20% 20%)")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                      title="Fixar"
                    >
                      <Pin size={12} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                      className="p-1 rounded-xl transition-all duration-150"
                      style={{ color: "hsl(215 15% 55%)" }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLButtonElement).style.background = "hsl(4 82% 20%)";
                        (e.currentTarget as HTMLButtonElement).style.color = "hsl(4 82% 65%)";
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                        (e.currentTarget as HTMLButtonElement).style.color = "hsl(215 15% 55%)";
                      }}
                      title="Excluir"
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>

        {/* Rodapé sidebar */}
        <div
          className="p-2 shrink-0"
        >
          {/* Avatar + nome do usuário */}
          {!isSidebarCollapsed && (
            <div
              className="flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl mb-1"
              style={{
                background: "#0b0f18ff",
              }}
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
                style={{ background: "hsl(214 60% 28%)", color: "hsl(0 0% 95%)" }}
              >
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate" style={{ color: "hsl(0 0% 90%)" }}>
                  {userProfile?.nome}
                </p>
                <p className="text-xs truncate" style={{ color: "hsl(4 82% 60%)" }}>
                  {userProfile?.setor}
                </p>
              </div>
            </div>
          )}

          <button
            onClick={handleLogout}
            className={`w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-sm transition-all duration-200 ${isSidebarCollapsed ? "justify-center" : "justify-start"}`}
            style={{ color: "hsl(4 82% 58%)" }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "hsl(4 82% 15%)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "transparent";
            }}
          >
            <LogOut size={16} strokeWidth={2} />
            {!isSidebarCollapsed && <span>Sair da conta</span>}
          </button>
        </div>
      </aside>

      {/* ══════════════ MAIN ══════════════ */}
      <main
        className="flex-1 flex flex-col min-w-0 min-h-0"
        style={{ marginLeft: window.innerWidth >= 768 ? (isSidebarCollapsed ? "60px" : "260px") : "0" }}
      >
        {/* Topbar mobile */}
        <div
          className="md:hidden flex items-center gap-3 px-4 py-3 shrink-0"
          style={{ borderBottom: "1px solid hsl(220 15% 16%)" }}
        >
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="flex items-center justify-center w-9 h-9 rounded-xl transition-all duration-200"
            style={{ color: "hsl(215 15% 68%)" }}
            onMouseEnter={e => (e.currentTarget.style.background = "hsl(220 20% 14%)")}
            onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
          >
            <img src={abrir} alt="Menu" className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "#da2316ff" }}
            >
              <img src={logo} alt="ViniAI Logo" className="w-[80%] h-[80%] object-contain" />
            </div>
            <span className="font-semibold text-sm">ViniAI</span>
          </div>
        </div>

        {/* Área de mensagens */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {!activeConversation || activeConversation.messages.length === 0 ? (
            <EmptyState onSuggestionClick={handleSend} setor={userProfile?.setor} />
          ) : (
            <div className="flex-1 overflow-y-auto py-6 px-4 md:px-6">
              <div className="max-w-4xl mx-auto space-y-6">
                {activeConversation.messages.map((msg) => (
                  <ChatMessage
                    key={msg.id}
                    id={msg.id}
                    content={msg.content}
                    role={msg.role}
                  />
                ))}
                {isTyping && (
                  <ChatMessage id="typing" content="" role="assistant" isTyping />
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}
        </div>

        {/* Input area */}
        <div
          className="shrink-1 px-4 md:px-6 pt-0 pb-1 md:pb-2"
        >
          <div className="max-w-4xl mx-auto">
            <ChatInput onSend={handleSend} disabled={!activeConversation || isTyping} />
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;