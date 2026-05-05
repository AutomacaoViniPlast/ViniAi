import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import { changePassword } from "../services/auth";
import { isTokenValid } from "../lib/storage";
import logoVini from "../image/logoviniai2.png";

function validatePassword(password: string): string | null {
  if (password.length < 8) return "A senha deve ter pelo menos 8 caracteres.";
  if (!/[A-Z]/.test(password)) return "A senha deve conter pelo menos uma letra maiúscula.";
  if (!/[a-z]/.test(password)) return "A senha deve conter pelo menos uma letra minúscula.";
  if (!/\d/.test(password)) return "A senha deve conter pelo menos um número.";
  return null;
}

const ChangePassword = () => {
  const navigate = useNavigate();

  if (!isTokenValid()) {
    navigate("/auth", { replace: true });
    return null;
  }

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const hasError = message.length > 0;

  const inputClass = (error: boolean) =>
    `w-full rounded-xl border bg-input px-5 py-3 text-sm outline-none transition-all placeholder:text-muted-foreground ${
      error
        ? "border-red-500 shadow-[0_0_0_3px_hsl(0_72%_51%/0.15)]"
        : "border-border focus:border-primary focus:shadow-[0_0_0_3px_hsl(var(--primary)/0.15)]"
    }`;

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setMessage("");

    const pwError = validatePassword(password);
    if (pwError) { setMessage(pwError); return; }

    if (password !== confirm) { setMessage("As senhas não coincidem."); return; }

    setLoading(true);
    try {
      await changePassword(password);
      window.location.href = "/";
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
                Defina uma senha pessoal para sua conta.
              </h2>
              <p className="mt-4 text-base leading-relaxed text-muted-foreground lg:ml-2">
                O administrador configurou uma senha temporária. Crie uma senha própria antes de continuar.
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
                Criar nova senha
              </h1>
              <p className="text-base text-muted-foreground">
                Defina uma senha pessoal para acessar o sistema.
              </p>
            </div>

            <form onSubmit={handleSubmit} noValidate>
              <div className="space-y-5">
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    placeholder="Nova senha"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={inputClass(hasError) + " pr-12"}
                    autoFocus
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

                <input
                  type={showPassword ? "text" : "password"}
                  placeholder="Confirmar nova senha"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className={inputClass(hasError)}
                />

                <p className="text-xs text-muted-foreground">
                  Mínimo 8 caracteres, com letra maiúscula, minúscula e número.
                </p>
              </div>

              {message && <p className="mt-5 text-center text-base text-red-500 animate-fade-in">{message}</p>}

              <button
                type="submit"
                disabled={loading}
                className="mt-6 w-full rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-primary-foreground transition-all hover:brightness-110 hover:shadow-[0_10px_24px_hsl(var(--primary)/0.35)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? "Aguarde..." : "Salvar senha"}
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
};

export default ChangePassword;
