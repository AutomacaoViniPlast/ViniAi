import { useState } from "react";
import { signIn, signUp, resetPassword } from "../services/auth";

type Mode = "login" | "register" | "reset";

const Auth = () => {
  const [mode, setMode] = useState<Mode>("login");
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    setLoading(true);
    setMessage("");

    try {
      if (mode === "login") {
        const data = await signIn(email, password);
        if (data.session) {
          window.location.href = "/";
        }
      }

      if (mode === "register") {
        if (!nome.trim()) {
          setMessage("Por favor, informe seu nome.");
          return;
        }
        await signUp(email, password, nome);
        setMessage("Conta criada! Verifique seu email para confirmar.");
      }

      if (mode === "reset") {
        await resetPassword(email);
        setMessage("Email de recuperação enviado!");
      }
    } catch (err: any) {
      setMessage(err.message || "Ocorreu um erro.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center h-screen bg-background text-white">
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 pt-16 w-full max-w-lg h-auto space-y-5">
        <h1 className="text-xl font-bold text-center">
          {mode === "login" && "Entrar"}
          {mode === "register" && "Criar conta"}
          {mode === "reset" && "Recuperar senha"}
        </h1>

        {mode === "register" && (
          <input
            type="text"
            placeholder="Seu nome"
            value={nome}
            onChange={(e) => setNome(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-3 text-sm outline-none focus:border-primary"
          />
        )}

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-3 text-sm outline-none focus:border-primary"
        />

        {mode !== "reset" && (
          <input
            type="password"
            placeholder="Senha"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-3 py-3 text-sm outline-none focus:border-primary"
          />
        )}

        {message && <p className="text-sm text-center text-yellow-400">{message}</p>}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full bg-primary py-2 rounded-xl text-sm font-medium disabled:opacity-50"
        >
          {loading ? "Aguarde..." : mode === "login" ? "Entrar" : mode === "register" ? "Criar conta" : "Enviar email"}
        </button>

        <div className="text-sm text-center text-zinc-400 space-y-3">
          {mode === "login" && (
            <>
              <p>
                Não tem conta?{" "}
                <button onClick={() => setMode("register")} className="text-white underline pl-1">Criar conta</button>
              </p>
              <p>
                <button onClick={() => setMode("reset")} className="text-white underline">Esqueci minha senha</button>
              </p>
            </>
          )}
          {mode !== "login" && (
            <p>
              <button onClick={() => setMode("login")} className="text-white underline">Voltar ao login</button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Auth;