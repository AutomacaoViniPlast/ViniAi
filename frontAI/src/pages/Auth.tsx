import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { signIn, signUp } from "../services/auth";

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
    <div className="flex items-center justify-center h-screen bg-background text-foreground">
      <div className="bg-card border border-border rounded-xl p-5 pt-16 w-full max-w-lg h-auto space-y-5">
        <h1 className="text-xl font-bold text-center">
          {mode === "login" && "Entrar"}
          {mode === "register" && "Criar conta"}
        </h1>

        {mode === "register" && (
          <input
            type="text"
            placeholder="Seu nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="w-full bg-input border border-border rounded-xl px-3 py-3 text-sm outline-none focus:border-primary text-foreground placeholder:text-muted-foreground"
          />
        )}

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-input border border-border rounded-xl px-3 py-3 text-sm outline-none focus:border-primary text-foreground placeholder:text-muted-foreground"
        />

        <div className="relative">
          <input
            type={showPassword ? "text" : "password"}
            placeholder="Senha"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-input border border-border rounded-xl px-3 py-3 pr-10 text-sm outline-none focus:border-primary text-foreground placeholder:text-muted-foreground"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>

        {message && <p className="text-sm text-center text-yellow-500">{message}</p>}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-primary text-primary-foreground py-2 rounded-xl text-sm font-medium disabled:opacity-50"
        >
          {loading ? "Aguarde..." : mode === "login" ? "Entrar" : "Criar conta"}
        </button>

        <div className="text-sm text-center text-muted-foreground space-y-3">
          {mode === "login" ? (
            <p>
              Não tem conta?
              <button onClick={() => setMode("register")} className="text-foreground underline pl-1">
                Criar conta
              </button>
            </p>
          ) : (
            <p>
              <button onClick={() => setMode("login")} className="text-foreground underline">
                Voltar ao login
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Auth;