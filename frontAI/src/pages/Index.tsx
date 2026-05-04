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
import logo2 from "../image/logoviniai2.png";
import abrir from "../image/abrir.png";
import { Pin, Pencil, Trash2, LogOut, Plus, MessageSquare, Search, PanelLeftClose, PanelLeftOpen, Sun, Moon, Menu, FileDown, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

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
  nivel_acesso?: string;
}

const Index = () => {
  const navigate = useNavigate();
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
  const [isDark, setIsDark] = useState(() => localStorage.getItem("vini-theme") !== "light");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  // Carrega perfil e conversas do banco de dados
  useEffect(() => {
    const user = getUser();
    setUserProfile({
      nome: user?.nome || "Usuário",
      setor: user?.setor || "GERAL",
      nivel_acesso: user?.nivel_acesso,
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

  // Carrega as mensagens ao selecionar uma conversa
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

  // Gerencia a alternância entre temas claro e escuro
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", isDark ? "dark" : "light");
    localStorage.setItem("vini-theme", isDark ? "dark" : "light");
  }, [isDark]);

  const toggleTheme = () => setIsDark(prev => !prev);

  // Cores inline reativamente ao tema
  const C = {
    bg: isDark ? "#111010ff" : "#c4c4c4",
    sidebar: isDark ? "#0d0d0d" : "#b5b5b5",
    sidebarBorder: isDark ? "#1e1e1e" : "#969696",
    card: isDark ? "#161616" : "#b8b8b8",
    searchBg: isDark ? "#0d0d0d" : "#b0b0b0",
    searchBorder: isDark ? "#1e1e1e" : "#8c8c8c",
    convActive: isDark ? "#1a1a1a" : "#a8a8a8",
    convHover: isDark ? "#1a1a1a" : "#a8a8a8",
    text: isDark ? "hsl(0 0% 95%)" : "#010101",
    textMuted: isDark ? "hsl(0 0% 58%)" : "#111111",
    textSubtle: isDark ? "hsl(0 0% 45%)" : "#222222",
    convText: isDark ? "hsl(0 0% 68%)" : "#050505",
    hoverBg: isDark ? "#1e1e1e" : "#a0a0a0",
    pinHover: isDark ? "#222222" : "#a0a0a0",
    loadingBg: isDark ? "#111111" : "#bdbdbd",
    topbarBorder: isDark ? "#1e1e1e" : "#a0a0a0",
    mobileMenuBg: isDark ? "#1a1a1a" : "#8a8a8a",
    redText: isDark ? "hsl(2 68% 58%)" : "hsl(0 72% 30%)",
    redHover: isDark ? "hsla(3, 35%, 22%, 1.00)" : "hsla(0, 72%, 40%, 0.15)",
    initials: "#572222ff",
  };

  const activeConversation = conversations.find((c) => c.id === activeId);

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    window.location.href = "/auth";
  };

  // Inicia uma nova conversa no sistema
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

  // Remove uma conversa do histórico
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

  // Fixa ou desafixa uma conversa na lista
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

  const startRenameConversation = (conversation: Conversation) => {
    setEditingConversationId(conversation.id);
    setEditingTitle(conversation.title);
  };

  const cancelRenameConversation = () => {
    setEditingConversationId(null);
    setEditingTitle("");
  };

  const submitRenameConversation = async (id: string) => {
    const trimmedTitle = editingTitle.trim();
    if (!trimmedTitle) {
      cancelRenameConversation();
      return;
    }

    try {
      await updateTitle(id, trimmedTitle);
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmedTitle } : c))
      );
      cancelRenameConversation();
    } catch (err) {
      console.error("Erro ao renomear conversa:", err);
      toast.error("Não foi possível atualizar o título.");
    }
  };

  const exportConversation = async (conv: Conversation) => {
    let messages = conv.messages;

    if (!conv.messagesLoaded) {
      try {
        const msgs = await getMessages(conv.id);
        messages = msgs.map((m) => ({ id: m.id, content: m.conteudo, role: m.role }));
      } catch {
        toast.error("Erro ao carregar mensagens para exportação.");
        return;
      }
    }

    const exportData = {
      conversa: conv.title,
      exportado_em: new Date().toLocaleString("pt-BR"),
      usuario: userProfile?.nome || "Usuário",
      setor: userProfile?.setor || "GERAL",
      total_mensagens: messages.length,
      mensagens: messages.map((m) => ({
        papel: m.role === "user" ? "usuario" : "assistente",
        conteudo: m.content,
      })),
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const safeName = conv.title.replace(/[^\w\s\-àáâãéêíóôõúüçÀÁÂÃÉÊÍÓÔÕÚÜÇ]/g, "").trim().slice(0, 50);
    a.download = `conversa_${safeName || conv.id}_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast.success("Conversa exportada com sucesso!");
  };

  // Envia a mensagem do usuário e processa a resposta da IA
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
      <div className="flex h-screen items-center justify-center transition-colors duration-300" style={{ background: C.loadingBg }}>
        <div className="flex flex-col items-center gap-6">
          <img src={logo2} alt="ViniAI Logo" className="w-20 h-20 object-contain animate-pulse" style={{ animationDuration: "1.5s" }} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-[100dvh] overflow-hidden" style={{ background: C.bg, color: C.text }}>

      {/* Camada de fundo para fechar o menu no mobile */}
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
          background: C.sidebar,
          borderRight: `1px solid ${C.sidebarBorder}`,
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
          className={`flex items-center justify-between ${isSidebarCollapsed ? "px-0" : "px-3"} pt-4 pb-2 shrink-0`}
          style={{ minHeight: "60px" }}
        >
          {!isSidebarCollapsed && (
            <>
              <div className="flex items-center gap-2.5 overflow-hidden">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: "hsl(2 72% 44%)" }}
                >
                  <img src={logo} alt="ViniAI Logo" className="w-6 h-6 object-contain mx-auto my-auto" />
                </div>
                <div className="overflow-hidden">
                  <p className="font-semibold text-sm leading-tight truncate" style={{ color: C.text }}>ViniAI</p>
                  <p className="text-xs truncate" style={{ color: C.textMuted }}>
                    {userProfile?.nome}
                    {userProfile?.setor && (
                      <span style={{ color: C.redText }}> · {userProfile.setor}</span>
                    )}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setIsSidebarCollapsed(true)}
                className="hidden md:flex items-center justify-center w-7 h-7 rounded-full transition-all duration-200 shrink-0"
                style={{ color: C.textMuted }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = C.hoverBg;
                  e.currentTarget.style.color = C.text;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = C.textMuted;
                }}
                title="Recolher"
              >
                <PanelLeftClose size={16} />
              </button>
              <button
                onClick={() => setIsSidebarOpen(false)}
                className="md:hidden flex items-center justify-center w-9 h-9 rounded-xl transition-all duration-200 mt-2"
                style={{
                  color: C.text,
                  background: "transparent",
                  border: "1px solid hsl(var(--border) / 0.15)"
                }}
              >
                <Menu size={22} strokeWidth={2.5} />
              </button>
            </>
          )}

          {isSidebarCollapsed && (
            <button
              onClick={() => setIsSidebarCollapsed(false)}
              onMouseEnter={() => setIsLogoHovered(true)}
              onMouseLeave={() => setIsLogoHovered(false)}
              className="hidden md:flex mx-auto items-center justify-center w-[38px] h-[38px] rounded-xl transition-all duration-200"
              style={{
                background: isLogoHovered ? "#2a2a2a" : "hsl(2 72% 44%)",
                color: "#fff",
              }}
              title="Expandir"
            >
              {isLogoHovered
                ? <PanelLeftOpen size={16} />
                : <img src={logo} alt="ViniAI Logo" className="w-[70%] h-[70%] object-contain" />
              }
            </button>
          )}
        </div>

        {/* Nova conversa */}
        <div className="px-2 pt-6 pb-0 shrink-0">
          <button
            onClick={createNewConversation}
            className={`flex items-center justify-center rounded-xl transition-all duration-200 ${isSidebarCollapsed ? "w-[38px] h-[38px] mx-auto" : "w-full gap-2 py-2.5 px-3 text-sm font-medium"}`}
            style={{ background: "hsl(2 72% 44%)", color: "#fff" }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "hsl(2 72% 38%)";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "0 4px 12px hsl(2 72% 44% / 0.35)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "hsl(2 72% 44%)";
              (e.currentTarget as HTMLButtonElement).style.boxShadow = "none";
            }}
          >
            <Plus size={isSidebarCollapsed ? 18 : 15} strokeWidth={2.5} />
            {!isSidebarCollapsed && <span>Nova Conversa</span>}
          </button>
        </div>

        {/* Search */}
        {!isSidebarCollapsed && (
          <div className="px-2 pt-2 pb-2 shrink-0">
            <div
              className="flex items-center gap-2 px-3 py-2 rounded-xl"
              style={{ background: C.searchBg, border: `1px solid ${C.searchBorder}` }}
            >
              <Search size={14} style={{ color: C.textMuted, flexShrink: 0 }} />
              <input
                type="text"
                placeholder="Buscar conversa..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-inherit"
                style={{ color: C.text, caretColor: "hsl(2 72% 44%)", opacity: 0.9 }}
              />
            </div>
          </div>
        )}

        {/* Lista de conversas */}
        <div className="flex-1 overflow-y-auto px-2 py-0.1 space-y-1">
          {!isSidebarCollapsed && filteredConversations.length > 0 && (
            <p className="text-xs font-medium px-2 py-1.5" style={{ color: C.textSubtle }}>
              Conversas
            </p>
          )}

          {filteredConversations.map((conv) => (
            <div
              key={conv.id}
              className={`group relative flex items-center transition-all duration-150 cursor-pointer ${isSidebarCollapsed ? "justify-center" : "gap-1 px-2.5 py-2.5 rounded-xl text-sm"}`}
              style={{
                background: activeId === conv.id ? C.convActive : "transparent",
                color: activeId === conv.id ? C.text : C.convText,
                width: isSidebarCollapsed ? "38px" : "auto",
                height: isSidebarCollapsed ? "38px" : "auto",
                margin: isSidebarCollapsed ? "4px auto" : "0",
                borderRadius: isSidebarCollapsed ? "12px" : "",
              }}
              onMouseEnter={e => {
                if (activeId !== conv.id)
                  (e.currentTarget as HTMLDivElement).style.background = C.convHover;
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
                      {conv.pinned && <Pin size={10} style={{ color: C.redText, flexShrink: 0 }} />}
                      {editingConversationId === conv.id ? (
                        <input
                          autoFocus
                          type="text"
                          value={editingTitle}
                          onClick={(e) => e.stopPropagation()}
                          onChange={(e) => setEditingTitle(e.target.value)}
                          onBlur={() => void submitRenameConversation(conv.id)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") void submitRenameConversation(conv.id);
                            if (e.key === "Escape") cancelRenameConversation();
                          }}
                          className="w-full bg-transparent text-[13px] outline-none"
                          style={{ color: C.text }}
                        />
                      ) : (
                        <span className="truncate text-[13px]">{conv.title}</span>
                      )}
                    </div>
                  </button>
                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); togglePin(conv.id); }}
                      className="p-1 rounded-xl transition-all duration-150"
                      style={{ color: conv.pinned ? C.redText : C.textMuted }}
                      onMouseEnter={e => (e.currentTarget.style.background = C.pinHover)}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                      title="Fixar"
                    >
                      <Pin size={12} />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        startRenameConversation(conv);
                      }}
                      className="p-1 rounded-xl transition-all duration-150"
                      style={{ color: C.textMuted }}
                      onMouseEnter={e => (e.currentTarget.style.background = C.pinHover)}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                      title="Editar título"
                    >
                      <Pencil size={12} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); void exportConversation(conv); }}
                      className="p-1 rounded-xl transition-all duration-150"
                      style={{ color: C.textMuted }}
                      onMouseEnter={e => (e.currentTarget.style.background = C.pinHover)}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                      title="Exportar conversa"
                    >
                      <FileDown size={12} />
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                      className="p-1 rounded-xl transition-all duration-150"
                      style={{ color: C.textMuted }}
                      onMouseEnter={e => {
                        (e.currentTarget as HTMLButtonElement).style.background = "hsl(2 60% 19%)";
                        (e.currentTarget as HTMLButtonElement).style.color = "hsl(2 68% 60%)";
                      }}
                      onMouseLeave={e => {
                        (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                        (e.currentTarget as HTMLButtonElement).style.color = C.textMuted;
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
              className="flex items-center gap-2 px-2.5 py-2.5 rounded-xl mb-1"
              style={{ background: C.card }}
            >
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0"
                style={{ background: C.initials, color: "hsl(0 0% 95%)" }}
              >
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate" style={{ color: C.text }}>
                  {userProfile?.nome}
                </p>
                <p className="text-xs truncate" style={{ color: C.redText }}>
                  {userProfile?.setor}
                </p>
              </div>
              {/* Botão alternar tema simplificado */}
              <button
                onClick={toggleTheme}
                title={isDark ? "Modo claro" : "Modo escuro"}
                className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-all duration-200"
                style={{
                  color: isDark ? "hsl(0 0% 70%)" : "#444",
                }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLButtonElement).style.background = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";
                  (e.currentTarget as HTMLButtonElement).style.color = isDark ? "#fff" : "#000";
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                  (e.currentTarget as HTMLButtonElement).style.color = isDark ? "hsl(0 0% 70%)" : "#444";
                }}
              >
                {isDark ? <Sun size={16} strokeWidth={1.5} /> : <Moon size={16} strokeWidth={1.5} />}
              </button>
            </div>
          )}

          {userProfile?.nivel_acesso === "ADMIN" && (
            <button
              onClick={() => navigate("/admin")}
              className={`w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-sm transition-all duration-200 ${isSidebarCollapsed ? "justify-center" : "justify-start"}`}
              style={{ color: C.textMuted }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.background = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";
                (e.currentTarget as HTMLButtonElement).style.color = C.text;
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                (e.currentTarget as HTMLButtonElement).style.color = C.textMuted;
              }}
            >
              <ShieldCheck size={16} strokeWidth={1.8} />
              {!isSidebarCollapsed && <span>Painel Admin</span>}
            </button>
          )}

          <button
            onClick={handleLogout}
            className={`w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-sm transition-all duration-200 ${isSidebarCollapsed ? "justify-center" : "justify-start"}`}
            style={{ color: C.redText }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = C.redHover;
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
        {/* Menu flutuante para dispositivos móveis */}
        <div className={`md:hidden absolute top-0 left-0 p-2 z-50 pointer-events-none w-full flex items-center ${isSidebarOpen ? "hidden" : ""}`}>
          {/* Botão Menu (Esquerda) */}
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="flex items-center justify-center w-11 h-11 rounded-xl transition-all duration-200 shrink-0 pointer-events-auto"
            style={{
              color: C.text,
              background: "transparent",
              border: "1px solid hsl(var(--border) / 0.15)"
            }}
          >
            <Menu size={22} strokeWidth={2.5} />
          </button>
        </div>

        {/* Exibe o histórico de mensagens ou a tela inicial */}
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

        <div className="shrink-0 px-3 sm:px-4 md:px-6 pt-6 sm:pt-8 md:pt-10 pb-2 md:pb-2">
          <div className="max-w-4xl mx-auto">
            <ChatInput onSend={handleSend} disabled={!activeConversation || isTyping} />
          </div>
        </div>
      </main>
    </div>
  );
};

export default Index;
