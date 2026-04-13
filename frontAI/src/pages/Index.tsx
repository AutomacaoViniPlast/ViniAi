import { useState, useEffect, useRef } from "react";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import EmptyState from "@/components/chat/EmptyState";
import { sendChatMessage } from "../services/n8n";
import {
  listConversations,
  createConversation,
  deleteConversation as apiDeleteConversation,
  togglePin as apiTogglePin,
  getMessages,
  saveMessage,
  updateTitle,
} from "../services/conversations";
import { getUser } from "../lib/storage";
import { toast } from "@/components/ui/sonner";

import logo from "../image/logoviniai.png";
import abrir from "../image/abrir.png";
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
  pinned: boolean;
  messagesLoaded: boolean;
}

interface UserProfile {
  nome: string;
  setor: string;
}

const Index = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [search, setSearch] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isLogoHovered, setIsLogoHovered] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(window.innerWidth < 768);
  const [carregando, setCarregando] = useState(true);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ── Carrega perfil + conversas do banco ──────────────────────────────────────
  useEffect(() => {
    const user = getUser();
    setUserProfile({
      nome: user?.nome || "Usuário",
      setor: user?.setor || "GERAL",
    });

    async function init() {
      try {
        const apiConvs = await listConversations();

        if (apiConvs.length > 0) {
          const convs: Conversation[] = apiConvs.map((c) => ({
            id: c.id,
            title: c.titulo,
            messages: [],
            createdAt: new Date(c.criado_em).getTime(),
            pinned: c.pinned,
            messagesLoaded: false,
          }));
          setConversations(convs);
          setActiveId(convs[0].id);
        } else {
          // Primeiro acesso — cria uma conversa inicial
          const nova = await createConversation();
          setConversations([{
            id: nova.id,
            title: nova.titulo,
            messages: [],
            createdAt: new Date(nova.criado_em).getTime(),
            pinned: false,
            messagesLoaded: true,
          }]);
          setActiveId(nova.id);
        }
      } catch (err) {
        console.error("Erro ao carregar conversas:", err);
        toast.error("Erro ao carregar conversas. Verifique sua conexão e tente novamente.");
      } finally {
        setCarregando(false);
      }
    }

    init();
  }, []);

  // ── Carrega mensagens ao trocar de conversa ───────────────────────────────────
  useEffect(() => {
    if (!activeId) return;

    const conv = conversations.find((c) => c.id === activeId);
    if (!conv || conv.messagesLoaded) return;

    getMessages(activeId)
      .then((msgs) => {
        setConversations((prev) =>
          prev.map((c) =>
            c.id === activeId
              ? {
                ...c,
                messagesLoaded: true,
                messages: msgs.map((m) => ({
                  id: m.id,
                  content: m.conteudo,
                  role: m.role,
                })),
              }
              : c
          )
        );
      })
      .catch((err) => console.error("Erro ao carregar mensagens:", err));
  }, [activeId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeId, conversations, isTyping]);

  useEffect(() => {
    const handleResize = () => setIsMobileViewport(window.innerWidth < 768);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const activeConversation = conversations.find((c) => c.id === activeId);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/auth";
  };

  // ── Nova conversa ─────────────────────────────────────────────────────────────
  const createNewConversation = async () => {
    try {
      const nova = await createConversation();
      const newConv: Conversation = {
        id: nova.id,
        title: nova.titulo,
        messages: [],
        createdAt: new Date(nova.criado_em).getTime(),
        pinned: false,
        messagesLoaded: true,
      };
      setConversations((prev) => [newConv, ...prev]);
      setActiveId(newConv.id);
      setIsSidebarOpen(false);
    } catch (err) {
      console.error("Erro ao criar conversa:", err);
      toast.error(
        err instanceof Error ? err.message : "Erro ao criar conversa. Tente novamente."
      );
    }
  };

  // ── Deletar conversa ──────────────────────────────────────────────────────────
  const deleteConversation = async (id: string) => {
    try {
      await apiDeleteConversation(id);
      setConversations((prev) => {
        const updated = prev.filter((c) => c.id !== id);
        if (id === activeId) setActiveId(updated[0]?.id || null);
        return updated;
      });
    } catch (err) {
      console.error("Erro ao deletar conversa:", err);
    }
  };

  // ── Alternar pin ──────────────────────────────────────────────────────────────
  const togglePin = async (id: string) => {
    try {
      const updated = await apiTogglePin(id);
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, pinned: updated.pinned } : c))
      );
    } catch (err) {
      console.error("Erro ao alternar pin:", err);
    }
  };

  // ── Enviar mensagem ───────────────────────────────────────────────────────────
  const handleSend = async (content: string) => {
    if (!activeConversation) return;

    const sessionId = activeConversation.id;
    const setor = userProfile?.setor || "GERAL";
    const isFirstMessage = activeConversation.messages.length === 0;

    // Atualiza título na primeira mensagem
    const novoTitulo = content.slice(0, 50);
    if (isFirstMessage) {
      updateTitle(sessionId, novoTitulo).catch(() => { });
    }

    // Adiciona mensagem do usuário no estado imediatamente
    const tempUserId = `temp_${Date.now()}`;
    setConversations((prev) =>
      prev.map((c) =>
        c.id === sessionId
          ? {
            ...c,
            title: isFirstMessage ? novoTitulo : c.title,
            messages: [...c.messages, { id: tempUserId, content, role: "user" }],
          }
          : c
      )
    );

    setIsTyping(true);

    // Grava mensagem do usuário no banco (em paralelo com a chamada ao n8n)
    saveMessage(sessionId, "user", content).catch(() => { });

    try {
      const data = await sendChatMessage(content, setor, sessionId);

      const responseText =
        data?.answer ||
        data?.message ||
        data?.output ||
        data?.response ||
        (typeof data === "string" ? data : "Sem resposta.");

      // Grava resposta da IA no banco
      saveMessage(sessionId, "assistant", responseText).catch(() => { });

      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? {
              ...c,
              messages: [
                ...c.messages,
                { id: `ai_${Date.now()}`, content: responseText, role: "assistant" },
              ],
            }
            : c
        )
      );
    } catch (error) {
      console.error(error);

      const errMsg = "Desculpe, tive um problema de conexão.";
      saveMessage(sessionId, "assistant", errMsg).catch(() => { });

      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? {
              ...c,
              messages: [
                ...c.messages,
                { id: `err_${Date.now()}`, content: errMsg, role: "assistant" },
              ],
            }
            : c
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
    <div className="flex h-[100dvh] overflow-hidden" style={{ background: "#09090fff", color: "hsl(0 0% 95%)" }}>

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
          width: isMobileViewport ? "82vw" : (isSidebarCollapsed ? "60px" : "290px"),
          maxWidth: isMobileViewport ? "300px" : "unset",
          background: "#07070eff",
          borderRight: "1px solid #23272fff",
          transition: "width 0.28s cubic-bezier(0.4,0,0.2,1)",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          position: "fixed" as const,
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 40,
          transform: isSidebarOpen || !isMobileViewport ? "translateX(0)" : "translateX(-100%)",
        }}
        className={`${isSidebarOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
      >
        {/* Sidebar header */}
        <div
          className="flex items-center justify-between px-3 pt-4 pb-2 shrink-0"
          style={{ minHeight: "60px" }}
        >
          {!isSidebarCollapsed && (
            <>
              <div className="flex items-center gap-2.5 overflow-hidden">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: "#c52318ff" }}
                >
                  <img src={logo} alt="ViniAI Logo" className="w-6 h-6 object-contain mx-auto my-auto" />
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
              <button
                onClick={() => setIsSidebarCollapsed(true)}
                className="hidden md:flex items-center justify-center w-7 h-7 rounded-full transition-all duration-200 shrink-0"
                style={{ color: "hsl(215 15% 58%)" }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = "hsla(219, 23%, 12%, 1.00)";
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
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="md:hidden flex items-center justify-center w-7 h-7 rounded-full"
                style={{ color: "hsl(215 15% 58%)" }}
              >
                ✕
              </button>
            </>
          )}

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
            style={{ background: "#b62015ff", color: "#fff" }}
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
                style={{ color: "hsl(0 0% 95%)", caretColor: "hsl(4 82% 47%)" }}
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
        <div className="p-2 shrink-0">
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
        style={{ marginLeft: isMobileViewport ? "0" : (isSidebarCollapsed ? "60px" : "260px") }}
      >
        {/* Topbar mobile */}
        <div
          className="md:hidden flex items-center justify-between gap-3 px-4 py-3 shrink-0"
          style={{ borderBottom: "1px solid hsl(220 15% 16%)" }}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="flex items-center justify-center w-9 h-9 rounded-xl transition-all duration-200 shrink-0"
              style={{ color: "hsl(215 15% 68%)" }}
              onMouseEnter={e => (e.currentTarget.style.background = "hsl(220 20% 14%)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <img src={abrir} alt="Menu" className="w-5 h-5" />
            </button>
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "#da2316ff" }}
            >
              <img src={logo} alt="ViniAI Logo" className="w-6 h-6 object-contain mx-auto my-auto" />
            </div>
            <span className="font-semibold text-sm truncate">ViniAI</span>
          </div>
          <div className="w-9 h-9 shrink-0" aria-hidden="true" />
        </div>

        {/* Área de mensagens */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {!activeConversation || activeConversation.messages.length === 0 ? (
            <EmptyState onSuggestionClick={handleSend} setor={userProfile?.setor} />
          ) : (
            <div className="flex-1 overflow-y-auto py-4 px-3 sm:px-4 md:px-6">
              <div className="max-w-4xl mx-auto space-y-5 md:space-y-6">
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

        <div className="shrink-0 px-3 sm:px-4 md:px-6 pt-0 pb-2 md:pb-2">
          <div className="max-w-4xl mx-auto">
            <ChatInput onSend={handleSend} disabled={!activeConversation || isTyping} />
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;
