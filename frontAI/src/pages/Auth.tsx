import { FormEvent, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
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

  const hasError = message.length > 0;

  const handleSubmit = async (event?: FormEvent<HTMLFormElement>) => {
    event?.preventDefault();
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
    <div className="h-screen overflow-hidden bg-background text-foreground px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
      <div className="mx-auto relative grid min-h-[calc(100vh-3rem)] w-full max-w-7xl overflow-hidden rounded-3xl border-0 bg-background shadow-none lg:grid-cols-[1.05fr_1fr] lg:border lg:border-border/70 lg:shadow-2xl lg:shadow-black/25">
        {/* Máscara de fundo global que desliza da esquerda para a direita */}
        <div className="pointer-events-none absolute inset-0 hidden lg:block">
          <div
            className="absolute inset-0 opacity-[0.1] [background-image:linear-gradient(hsl(var(--foreground)/0.2)_1px,transparent_1px),linear-gradient(90deg,hsl(var(--foreground)/0.2)_1px,transparent_1px)] [background-size:34px_34px]"
            style={{ WebkitMaskImage: "linear-gradient(to right, black 8%, transparent 78%)", maskImage: "linear-gradient(to right, black 8%, transparent 78%)" }}
          />
        </div>

        <section className="relative hidden flex-col justify-center p-8 lg:flex xl:p-10 z-10">
          <div className="relative z-10 -mt-16">
            <div className="mb-10 flex items-center gap-4">
              <img src={logoVini} alt="ViniAI Logo" className="h-12 w-12 object-contain drop-shadow-[0_10px_24px_hsl(0_0%_0%/0.4)]" />
              <div>
                <p className="text-base font-semibold tracking-wide">ViniAI</p>
                <p className="text-sm text-muted-foreground">Plataforma de IA Industrial</p>
              </div>
            </div>

            <div className="ml-12 min-w-[540px] max-w-3xl">
              <h2 className="text-[2.5rem] font-semibold leading-[1.15]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                Analise dados de produção com velocidade e contexto.
              </h2>
              <p className="mt-4 text-base leading-relaxed text-muted-foreground lg:ml-2">
                Entre para continuar suas conversas com o LLM, acompanhar históricos e transformar perguntas em decisões operacionais.
              </p>
            </div>
          </div>
        </section>

        <section className="relative flex items-center justify-center bg-transparent p-4 sm:p-6 md:p-8 z-10">
          <div className="w-full max-w-3xl lg:mr-16 rounded-3xl border-2 border-border/70 bg-card p-7 shadow-[0_20px_40px_hsl(0_0%_0%/0.24)] sm:p-10 relative z-20">
            <div className="mb-6 flex items-center justify-center gap-2.5 lg:hidden">
              <img src={logoVini} alt="ViniAI Logo" className="relative -translate-y-0.5 h-9 w-9 object-contain" />
              <span className="text-[0.95rem] font-semibold tracking-wide">ViniAI</span>
            </div>

            <div className="mb-8 space-y-2 text-center">
              <h1 className="text-3xl font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                {mode === "login" ? "Acesse sua conta" : "Crie sua conta"}
              </h1>
              <p className="text-base text-muted-foreground">
                {mode === "login"
                  ? "Continue sua conversa com a IA da ViniAI."
                  : "Configure seu acesso para iniciar novas conversas."}
              </p>
            </div>

            <form onSubmit={handleSubmit} noValidate>
              <div className="space-y-5">
                {mode === "register" && (
                  <input
                    type="text"
                    placeholder="Seu nome"
                    value={nome}
                    onChange={(e) => setNome(e.target.value)}
                    className={`w-full rounded-xl border bg-input px-5 py-3 text-sm outline-none transition-all placeholder:text-muted-foreground ${hasError
                        ? "border-red-500 shadow-[0_0_0_3px_hsl(0_72%_51%/0.15)]"
                        : "border-border focus:border-primary focus:shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]"
                      }`}
                  />
                )}

                <input
                  type="email"
                  placeholder="Email corporativo"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={`w-full rounded-xl border bg-input px-5 py-3 text-sm outline-none transition-all placeholder:text-muted-foreground ${hasError
                      ? "border-red-500 shadow-[0_0_0_3px_hsl(0_72%_51%/0.15)]"
                      : "border-border focus:border-primary focus:shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]"
                    }`}
                />

                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="Senha"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={`w-full rounded-xl border bg-input px-5 py-3 pr-12 text-sm outline-none transition-all placeholder:text-muted-foreground ${hasError
                        ? "border-red-500 shadow-[0_0_0_3px_hsl(0_72%_51%/0.15)]"
                        : "border-border focus:border-primary focus:shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]"
                      }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                  </button>
                </div>
              </div>

              {message && <p className="mt-5 text-center text-base text-red-500 animate-fade-in">{message}</p>}

              <button
                type="submit"
                disabled={loading}
                className="mt-6 w-full rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition-all hover:brightness-110 hover:shadow-[0_10px_24px_hsl(var(--primary)/0.35)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Aguarde..." : mode === "login" ? "Entrar" : "Criar conta"}
              </button>
            </form>

            <div className="mt-6 text-center text-base text-muted-foreground">
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