import { useState, useEffect, useRef } from "react";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import EmptyState from "@/components/chat/EmptyState";
import ProfileEdit from "@/components/ProfileEdit";
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
import { getMe } from "../services/auth";
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
  photo?: string;
}

const Index = () => {
  const navigate = useNavigate();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState(false);
  const [search, setSearch] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(290);
  const [isResizingActive, setIsResizingActive] = useState(false);
  const lastExpandedWidth = useRef(290);
  const isSidebarCollapsed = sidebarWidth < 170;
  const [isLogoHovered, setIsLogoHovered] = useState(false);
  const [isMobileViewport, setIsMobileViewport] = useState(window.innerWidth < 768);
  const [carregando, setCarregando] = useState(true);
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [isDark, setIsDark] = useState(() => localStorage.getItem("vini-theme") !== "light");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const [editingConversationId, setEditingConversationId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [isProfileEditing, setIsProfileEditing] = useState(false);

  const handleSaveProfile = (data: { nome: string; setor: string; photo?: string | null }) => {
    if (!userProfile) return;
    
    // Se data.photo for undefined, mantém a atual. Se for null, remove. Se for string, atualiza.
    const newPhoto = data.photo === undefined ? userProfile.photo : data.photo;

    const updatedProfile = {
      ...userProfile,
      nome: data.nome,
      setor: data.setor,
      photo: newPhoto || undefined
    };
    
    // Persiste no localStorage
    const storedUser = getUser();
    if (storedUser) {
      localStorage.setItem("user", JSON.stringify({
        ...storedUser,
        nome: data.nome,
        setor: data.setor,
        photo: newPhoto || undefined
      }));
    }

    setUserProfile(updatedProfile);
    toast.success("Perfil atualizado com sucesso!");
  };

  // Carrega perfil e conversas do banco de dados
  useEffect(() => {
    const user = getUser();
    setUserProfile({
      nome: user?.nome || "Usuário",
      setor: user?.setor || "GERAL",
      nivel_acesso: user?.nivel_acesso,
      photo: user?.photo, // Carrega a foto salva
    });

    async function init() {
      try {
        const { user: freshUser } = await getMe();
        if (freshUser.force_password_change) {
          navigate("/change-password", { replace: true });
          return;
        }
      } catch {
        // se getMe falhar, continua normalmente
      }

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

  // Cores inline reativas ao tema via variáveis CSS
  const C = {
    bg: "var(--app-bg)",
    sidebar: "hsl(var(--sidebar))",
    sidebarBorder: "hsl(var(--border))",
    card: "hsl(var(--card))",
    searchBg: "hsl(var(--input))",
    searchBorder: "hsl(var(--border))",
    convActive: "hsl(var(--accent))",
    convHover: "hsl(var(--muted))",
    text: "hsl(var(--foreground))",
    textMuted: "hsl(var(--muted-foreground))",
    textSubtle: "hsl(var(--muted-foreground))",
    textLabel: isDark ? "hsl(0 0% 80%)" : "hsl(0 0% 38%)",
    convText: "hsl(var(--foreground))",
    hoverBg: "hsl(var(--muted))",
    pinHover: "hsl(var(--muted))",
    loadingBg: "hsl(var(--background))",
    topbarBorder: "hsl(var(--border))",
    mobileMenuBg: "hsl(var(--sidebar))",
    redText: "hsl(var(--primary))",
    redHover: "hsl(var(--primary) / 0.15)",
    initials: "hsl(var(--primary))",
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

  const handleResizeMouseDown = (e: React.MouseEvent) => {
    if (isMobileViewport) return;
    e.preventDefault();
    setIsResizingActive(true);
    const startX = e.clientX;
    const startWidth = sidebarWidth;

    const onMouseMove = (ev: MouseEvent) => {
      const newWidth = Math.min(300, Math.max(60, startWidth + ev.clientX - startX));
      setSidebarWidth(newWidth);
      if (newWidth >= 170) lastExpandedWidth.current = newWidth;
    };

    const onMouseUp = () => {
      setIsResizingActive(false);
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
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
    ? userProfile.nome
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2)
    : "AI";

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
          width: isMobileViewport ? "82vw" : `${sidebarWidth}px`,
          maxWidth: isMobileViewport ? "300px" : "unset",
          background: C.sidebar,
          borderRight: `1px solid ${C.sidebarBorder}`,
          transition: isResizingActive ? "none" : "width 0.28s cubic-bezier(0.4,0,0.2,1)",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          position: "fixed" as const,
          top: 0,
          bottom: 0,
          left: 0,
          zIndex: 40,
          overflow: "hidden",
          transform: isSidebarOpen || !isMobileViewport ? "translateX(0)" : "translateX(-100%)",
        }}
        className={`${isSidebarOpen ? "translate-x-0" : "-translate-x-full"} md:translate-x-0`}
      >
        {/* Handle de redimensionamento — apenas desktop */}
        {!isMobileViewport && (
          <div
            onMouseDown={handleResizeMouseDown}
            className="sidebar-resize-handle"
          />
        )}
        {/* Cabeçalho da Sidebar */}
        <div
          className="flex items-center gap-2.5 px-3 pt-4 pb-2 shrink-0 overflow-hidden whitespace-nowrap"
          style={{ minHeight: "60px", justifyContent: isSidebarCollapsed ? "center" : "flex-start" }}
        >
          {isSidebarCollapsed ? (
            /* Modo colapsado: logo visível por padrão, ícone de expandir aparece ao hover (sobrepostos) */
            <button
              onClick={() => {
                const defaultWidth = 290;
                setSidebarWidth(defaultWidth);
                lastExpandedWidth.current = defaultWidth;
              }}
              className="sidebar-collapsed-toggle w-10 h-10 rounded-xl shrink-0 transition-all duration-200"
              style={{ background: "hsl(var(--primary))", position: "relative" }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLButtonElement).style.background = C.hoverBg;
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLButtonElement).style.background = "hsl(var(--primary))";
              }}
              title="Expandir sidebar"
            >
              {/* Logo — visível por padrão */}
              <span
                className="sidebar-collapsed-logo"
                style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", transition: "opacity 0.2s ease", opacity: 1 }}
              >
                <img src={logo} alt="ViniAI Logo" className="w-6 h-6 object-contain" />
              </span>
              {/* Ícone abrir — visível ao hover */}
              <span
                className="sidebar-collapsed-icon"
                style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", transition: "opacity 0.2s ease", opacity: 0 }}
              >
                <PanelLeftOpen size={18} color="#fff" />
              </span>
            </button>
          ) : (
            /* Modo expandido: logo + nome + botão fechar */
            <>
              <div className="flex items-center gap-2.5 flex-1 min-w-0 overflow-hidden">
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
                  style={{ background: "hsl(var(--primary))" }}
                >
                  <img src={logo} alt="ViniAI Logo" className="w-6 h-6 object-contain" />
                </div>
                <div className="flex-1 min-w-0 overflow-hidden">
                  <p className="font-semibold text-sm leading-tight truncate" style={{ color: C.text }}>ViniAI</p>
                  <p className="text-[11px] truncate" style={{ color: C.textMuted }}>
                    {userProfile?.nome} <span style={{ color: C.redText, fontWeight: 700 }}>•{userProfile?.setor}</span>
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  lastExpandedWidth.current = sidebarWidth;
                  setSidebarWidth(60);
                }}
                className="hidden md:flex items-center justify-center w-8 h-8 rounded-full transition-all duration-200 shrink-0"
                style={{ color: C.textMuted }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = C.hoverBg;
                  e.currentTarget.style.color = C.text;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = C.textMuted;
                }}
                title="Recolher sidebar"
              >
                <PanelLeftClose size={16} />
              </button>
            </>
          )}
        </div>

        {/* Botão Nova Conversa */}
        <div className="px-2 pt-4 pb-0 shrink-0" style={{ display: "flex", justifyContent: isSidebarCollapsed ? "center" : "stretch" }}>
          <button
            onClick={createNewConversation}
            className="flex items-center justify-center rounded-xl"
            style={{
              background: "hsl(var(--primary))",
              color: "#fff",
              boxShadow: "none",
              overflow: "hidden",
              width: isSidebarCollapsed ? "40px" : "100%",
              height: "40px",
              padding: isSidebarCollapsed ? "0" : "0 12px",
              gap: isSidebarCollapsed ? "0" : "8px",
              fontSize: "0.875rem",
              fontWeight: 500,
              transition: "width 0.28s cubic-bezier(0.4,0,0.2,1), padding 0.28s cubic-bezier(0.4,0,0.2,1), gap 0.28s cubic-bezier(0.4,0,0.2,1), background 0.2s ease",
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "hsl(var(--primary-hover))";
              (e.currentTarget as HTMLButtonElement).style.filter = "brightness(1)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.background = "hsl(var(--primary))";
              (e.currentTarget as HTMLButtonElement).style.filter = "brightness(1)";
            }}
          >
            <Plus size={15} strokeWidth={2.5} style={{ flexShrink: 0 }} />
            {/* Texto: maxWidth colapsa para não empurrar o ícone + para fora; slide-in ao expandir */}
            <span
              style={{
                maxWidth: isSidebarCollapsed ? "0px" : "160px",
                opacity: isSidebarCollapsed ? 0 : 1,
                overflow: "hidden",
                whiteSpace: "nowrap",
                transform: isSidebarCollapsed ? "translateX(-4px)" : "translateX(0)",
                pointerEvents: isSidebarCollapsed ? "none" : "auto",
                transition: isSidebarCollapsed
                  ? "max-width 0.22s cubic-bezier(0.4,0,0.2,1), opacity 0.08s ease, transform 0.08s ease"
                  : "max-width 0.28s cubic-bezier(0.4,0,0.2,1), opacity 0.2s ease 0.16s, transform 0.22s cubic-bezier(0.34,1.56,0.64,1) 0.14s",
              }}
            >
              Nova Conversa
            </span>
          </button>
        </div>

        {/* Botão de busca no modo colapsado */}
        {isSidebarCollapsed && (
          <div className="px-2 pt-4 pb-3 shrink-0 flex justify-center">
            <button
              onClick={() => {
                /* Sempre expande para 290px (posição padrão da sidebar) */
                const w = 290;
                lastExpandedWidth.current = w;
                setSidebarWidth(w);
                setTimeout(() => searchInputRef.current?.focus(), 300);
              }}
              className="flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200"
              style={{ background: C.searchBg, color: C.textMuted }}
              onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = C.convHover; }}
              onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = C.searchBg; }}
            >
              <Search size={16} />
            </button>
          </div>
        )}

        {/* Search */}
        {!isSidebarCollapsed && (
          <div className="px-2 pt-4 pb-0 shrink-0">
            <div
              className="flex items-center gap-2 px-3 py-2.5 rounded-xl"
              style={{ background: C.searchBg, border: `0 ${C.searchBorder}` }}
            >
              <Search size={14} style={{ color: C.textMuted, flexShrink: 0 }} />
              <input
                ref={searchInputRef}
                type="text"
                placeholder="Buscar conversa..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="flex-1 bg-transparent text-sm outline-none placeholder:text-inherit"
                style={{ color: C.text, opacity: 0.8 }}
              />
            </div>
          </div>
        )}

        {/* Lista de conversas */}
        <div className="flex-1 overflow-y-auto px-2 pt-2 space-y-1">
          {!isSidebarCollapsed && filteredConversations.length > 0 && (
            <p className="text-xs font-medium px-2 py-1.5" style={{ color: C.textLabel }}>
              Conversas
            </p>
          )}

          {filteredConversations.map((conv) => {
            /* Durante resize ou colapsado: se a sidebar for estreita demais para mostrar texto,
               mostra apenas ícones centralizados — mesmo durante a transição de redimensionamento */
            const showIconOnly = isSidebarCollapsed;
            return (
              <div
                key={conv.id}
                className={`group relative flex items-center transition-all duration-150 cursor-pointer ${showIconOnly ? "justify-center" : "gap-1 px-2.5 py-2.5 rounded-xl text-sm"
                  }`}
                style={{
                  background: activeId === conv.id ? C.convActive : "transparent",
                  color: activeId === conv.id ? C.text : C.convText,
                  width: showIconOnly ? "40px" : "auto",
                  height: showIconOnly ? "40px" : "auto",
                  margin: showIconOnly ? "2px auto" : "0",
                  borderRadius: "12px",
                  overflow: "hidden",
                  flexShrink: 0,
                }}
                onMouseEnter={e => {
                  if (activeId !== conv.id) {
                    (e.currentTarget as HTMLDivElement).style.background = C.convHover;
                    (e.currentTarget as HTMLDivElement).style.filter = "brightness(1.3)";
                  }
                }}
                onMouseLeave={e => {
                  if (activeId !== conv.id) {
                    (e.currentTarget as HTMLDivElement).style.background = "transparent";
                    (e.currentTarget as HTMLDivElement).style.filter = "brightness(1)";
                  }
                }}
              >
                {showIconOnly ? (
                  <button
                    onClick={() => { setActiveId(conv.id); setIsSidebarOpen(false); }}
                    className="w-full flex justify-center items-center"
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
                    <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-150 shrink-0">
                      <button
                        onClick={(e) => { e.stopPropagation(); togglePin(conv.id); }}
                        className="p-1 rounded-xl transition-all duration-150"
                        style={{ color: conv.pinned ? C.redText : "hsl(var(--foreground) / 0.8)" }}
                        onMouseEnter={e => {
                          e.currentTarget.style.background = C.pinHover;
                          if (!conv.pinned) e.currentTarget.style.color = C.text;
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.background = "transparent";
                          if (!conv.pinned) e.currentTarget.style.color = C.text;
                        }}
                        title="Fixar"
                      >
                        <Pin size={13} strokeWidth={2} />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          startRenameConversation(conv);
                        }}
                        className="p-1 rounded-xl transition-all duration-150"
                        style={{ color: "hsl(var(--foreground) / 0.8)" }}
                        onMouseEnter={e => {
                          e.currentTarget.style.background = C.pinHover;
                          e.currentTarget.style.color = C.text;
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.background = "transparent";
                          e.currentTarget.style.color = "hsl(var(--foreground) / 0.8)";
                        }}
                        title="Editar título"
                      >
                        <Pencil size={13} strokeWidth={2} />
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
                        className="p-1 rounded-xl transition-all duration-150"
                        style={{ color: "hsl(var(--foreground) / 0.8)" }}
                        onMouseEnter={e => {
                          (e.currentTarget as HTMLButtonElement).style.background = "hsl(var(--destructive) / 0.15)";
                          (e.currentTarget as HTMLButtonElement).style.color = "hsl(var(--destructive))";
                        }}
                        onMouseLeave={e => {
                          (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                          (e.currentTarget as HTMLButtonElement).style.color = "hsl(var(--foreground) / 0.8)";
                        }}
                        title="Excluir"
                      >
                        <Trash2 size={13} strokeWidth={2} />
                      </button>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* Rodapé da Sidebar */}
        <div className="p-2 shrink-0">
          {isSidebarCollapsed ? (
            /* Modo colapsado: avatar + sair como ícones 40×40px centralizados */
            <div className="flex flex-col gap-1 items-center">
              {/* Avatar com iniciais — só o círculo, sem fundo extra */}
              <div
                className="flex items-center justify-center w-10 h-10 relative group"
                title={userProfile?.nome}
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 overflow-hidden"
                  style={{ background: userProfile?.photo ? "transparent" : C.initials, color: "hsl(0 0% 95%)" }}
                >
                  {userProfile?.photo ? (
                    <img src={userProfile.photo} alt="" className="w-full h-full object-cover" />
                  ) : (
                    initials
                  )}
                </div>
                {/* Botão de editar perfil colapsado */}
                <button
                  onClick={() => setIsProfileEditing(true)}
                  className="absolute inset-0 flex items-center justify-center bg-black/10 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                >
                  <Pencil size={12} color="#ffffffff" />
                </button>
              </div>
              {userProfile?.nivel_acesso === "ADMIN" && (
                <button
                  onClick={() => navigate("/admin")}
                  title="Painel Admin"
                  className="flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200"
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
                </button>
              )}
              <button
                onClick={handleLogout}
                title="Sair da conta"
                className="flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200"
                style={{ color: C.redText }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLButtonElement).style.background = C.redHover;
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                }}
              >
                <LogOut size={16} strokeWidth={2} />
              </button>
            </div>
          ) : (
            /* Modo expandido: perfil + tema + admin + sair */
            <>
              <div
                className="flex items-center gap-2 px-2.5 py-2.5 rounded-xl mb-1"
                style={{ background: C.searchBg }}
              >
                <div className="relative group shrink-0">
                  <div
                    className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold overflow-hidden"
                    style={{ background: userProfile?.photo ? "transparent" : C.initials, color: "hsl(0 0% 95%)" }}
                  >
                    {userProfile?.photo ? (
                      <img src={userProfile.photo} alt="" className="w-full h-full object-cover" />
                    ) : (
                      initials
                    )}
                  </div>
                  {/* Botão de editar perfil expandido */}
                  <button
                    onClick={() => setIsProfileEditing(true)}
                    className="absolute inset-0 flex items-center justify-center bg-black/40 rounded-full opacity-0 group-hover:opacity-100 transition-opacity duration-200"
                    title="Editar perfil"
                  >
                    <Pencil size={12} color="#fff" />
                  </button>
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
                    color: "hsl(var(--foreground) / 0.8)",
                  }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = isDark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.05)";
                    (e.currentTarget as HTMLButtonElement).style.color = C.text;
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                    (e.currentTarget as HTMLButtonElement).style.color = "hsl(var(--foreground) / 0.8)";
                  }}
                >
                  {isDark ? <Sun size={15} strokeWidth={2} /> : <Moon size={15} strokeWidth={2} />}
                </button>
              </div>

              {userProfile?.nivel_acesso === "ADMIN" && (
                <button
                  onClick={() => navigate("/admin")}
                  className="w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-sm transition-all duration-200 justify-start"
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
                  <span>Painel Admin</span>
                </button>
              )}

              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2.5 px-2.5 py-2.5 rounded-xl text-sm transition-all duration-200 justify-start"
                style={{ color: C.redText }}
                onMouseEnter={e => {
                  (e.currentTarget as HTMLButtonElement).style.background = C.redHover;
                }}
                onMouseLeave={e => {
                  (e.currentTarget as HTMLButtonElement).style.background = "transparent";
                }}
              >
                <LogOut size={16} strokeWidth={2} />
                <span>Sair da conta</span>
              </button>
            </>
          )}
        </div>
      </aside>

      {/* ══════════════ MAIN ══════════════ */}
      <main
        className="flex-1 flex flex-col min-w-0 min-h-0"
        style={{ marginLeft: isMobileViewport ? "0" : `${sidebarWidth}px`, transition: isResizingActive ? "none" : "margin-left 0.28s cubic-bezier(0.4,0,0.2,1)" }}
      >
        {/* Menu flutuante para dispositivos móveis */}
        {!isProfileEditing && (
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
        )}

        {/* Exibe o histórico de mensagens, a tela inicial ou edição de perfil */}
        <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
          {isProfileEditing ? (
            <ProfileEdit
              user={userProfile}
              onClose={() => setIsProfileEditing(false)}
              onSave={handleSaveProfile}
            />
          ) : !activeConversation || activeConversation.messages.length === 0 ? (
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

        {!isProfileEditing && (
          <div className="shrink-0 px-3 sm:px-4 md:px-6 pt-6 sm:pt-8 md:pt-10 pb-2 md:pb-2">
            <div className="max-w-4xl mx-auto">
              <ChatInput onSend={handleSend} disabled={!activeConversation || isTyping} />
            </div>
          </div>
        )}
      </main>

    </div>
  );
};

export default Index;
