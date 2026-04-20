import { useState } from "react";
import { Eye, EyeOff, MessageSquare, ShieldCheck, Sparkles } from "lucide-react";
import { signIn, signUp } from "../services/auth";
import logoVini from "../image/logoviniai2.png";

type Mode = "login" | "register";

const Auth = () => {
  const [mode, setMode] = useState<Mode>("login");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    setMessage("");

    try {
      if (mode === "login") {
        const data = await signIn(email, password);
        if (data.token) {
          window.location.href = "/";
        }
      }

      if (mode === "register") {
        if (!nome.trim()) {
          setMessage("Por favor, informe seu nome.");
          setLoading(false);
          return;
        }

        const data = await signUp(email, password, nome);
        if (data.token) {
          window.location.href = "/";
        }
      }
    } catch (err) {
      const error = err as Error;
      setMessage(error.message || "Ocorreu um erro.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
      <div className="mx-auto relative grid min-h-[calc(100vh-3rem)] w-full max-w-6xl overflow-hidden rounded-3xl border border-border/70 bg-background shadow-2xl shadow-black/25 lg:grid-cols-[1.05fr_1fr]">
        {/* Máscara de fundo global que desliza da esquerda para a direita */}
        <div className="pointer-events-none absolute inset-0 hidden lg:block">
          <div 
            className="absolute inset-0 opacity-[0.06] [background-image:linear-gradient(hsl(var(--foreground)/0.16)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--foreground)/0.16)_1px,transparent_1px)] [background-size:34px_34px]" 
            style={{ WebkitMaskImage: "linear-gradient(to right, black 15%, transparent 75%)", maskImage: "linear-gradient(to right, black 15%, transparent 75%)" }}
          />
        </div>

        <section className="relative hidden flex-col justify-between p-8 lg:flex xl:p-10 z-10">
          <div className="relative z-10">
            <div className="mb-10 flex items-center gap-3">
              <img src={logoVini} alt="ViniAI Logo" className="h-11 w-11 object-contain" />
              <div>
                <p className="text-sm font-semibold tracking-wide">ViniAI</p>
                <p className="text-xs text-muted-foreground">Plataforma conversacional industrial</p>
              </div>
            </div>

            <h2 className="max-w-md text-[2rem] font-semibold leading-[1.15]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              Analise dados de producao com velocidade e contexto.
            </h2>
            <p className="mt-4 max-w-md text-sm leading-relaxed text-muted-foreground">
              Entre para continuar suas conversas com o LLM, acompanhar historicos e transformar perguntas em decisoes operacionais.
            </p>
          </div>

          <div className="relative z-10 space-y-3">
            <div className="flex items-center gap-3 rounded-2xl border border-border/70 bg-background/35 p-3 transition-all duration-200 hover:-translate-y-0.5 hover:bg-background/55 hover:shadow-[0_8px_18px_rgba(0,0,0,0.28)]">
              <MessageSquare size={16} className="text-primary" />
              <p className="text-xs text-muted-foreground">Historico unificado das conversas</p>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-border/70 bg-background/35 p-3 transition-all duration-200 hover:-translate-y-0.5 hover:bg-background/55 hover:shadow-[0_8px_18px_rgba(0,0,0,0.28)]">
              <ShieldCheck size={16} className="text-primary" />
              <p className="text-xs text-muted-foreground">Acesso seguro por autenticacao</p>
            </div>
            <div className="flex items-center gap-3 rounded-2xl border border-border/70 bg-background/35 p-3 transition-all duration-200 hover:-translate-y-0.5 hover:bg-background/55 hover:shadow-[0_8px_18px_rgba(0,0,0,0.28)]">
              <Sparkles size={16} className="text-primary" />
              <p className="text-xs text-muted-foreground">Experiencia consistente com o chat principal</p>
            </div>
          </div>
        </section>

        <section className="relative flex items-center justify-center bg-transparent p-4 sm:p-6 md:p-8 z-10">
          <div className="w-full max-w-md rounded-2xl border border-border/70 bg-card p-5 shadow-xl shadow-black/20 sm:p-7 relative z-20">
            <div className="mb-6 flex items-center justify-center gap-2 lg:hidden">
              <img src={logoVini} alt="ViniAI Logo" className="h-8 w-8 object-contain" />
              <span className="text-sm font-semibold tracking-wide">ViniAI</span>
            </div>

            <div className="mb-6 space-y-2 text-center">
              <h1 className="text-2xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                {mode === "login" ? "Acesse sua conta" : "Crie sua conta"}
              </h1>
              <p className="text-sm text-muted-foreground">
                {mode === "login"
                  ? "Continue sua conversa com a IA da ViniAI."
                  : "Configure seu acesso para iniciar novas conversas."}
              </p>
            </div>

            <div className="space-y-4">
              {mode === "register" && (
                <input
                  type="text"
                  placeholder="Seu nome"
                  value={nome}
                  onChange={(e) => setNome(e.target.value)}
                  className="w-full rounded-xl border border-border bg-input px-4 py-3 text-sm outline-none transition-all focus:border-primary focus:shadow-[0_0_0_3px_hsl(var(--primary)/0.15)] placeholder:text-muted-foreground"
                />
              )}

              <input
                type="email"
                placeholder="Email corporativo"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-xl border border-border bg-input px-4 py-3 text-sm outline-none transition-all focus:border-primary focus:shadow-[0_0_0_3px_hsl(var(--primary)/0.15)] placeholder:text-muted-foreground"
              />

              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Senha"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-border bg-input px-4 py-3 pr-11 text-sm outline-none transition-all focus:border-primary focus:shadow-[0_0_0_3px_hsl(var(--primary)/0.15)] placeholder:text-muted-foreground"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>

            {message && <p className="mt-4 text-center text-sm text-yellow-500">{message}</p>}

            <button
              onClick={handleSubmit}
              disabled={loading}
              className="mt-5 w-full rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-primary-foreground transition-all hover:brightness-110 hover:shadow-[0_10px_24px_hsl(var(--primary)/0.35)] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {loading ? "Aguarde..." : mode === "login" ? "Entrar" : "Criar conta"}
            </button>

            <div className="mt-5 text-center text-sm text-muted-foreground">
              {mode === "login" ? (
                <p>
                  Nao tem conta?
                  <button
                    onClick={() => setMode("register")}
                    className="ml-1 font-medium text-foreground transition-colors hover:text-primary"
                  >
                    Criar conta
                  </button>
                </p>
              ) : (
                <p>
                  Ja possui conta?
                  <button
                    onClick={() => setMode("login")}
                    className="ml-1 font-medium text-foreground transition-colors hover:text-primary"
                  >
                    Voltar ao login
                  </button>
                </p>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
};

export default Auth;