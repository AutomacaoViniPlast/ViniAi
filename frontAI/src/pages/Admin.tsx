import { useState, useEffect, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Pencil, ChevronLeft, Check, X } from "lucide-react";
import { listUsers, createUser, updateUser, type AdminUser } from "../services/admin";
import logoVini from "../image/logoviniai2.png";

const SETORES = ["PRODUCAO","GERAL"];
const NIVEIS = ["usuario", "ADMIN"];

function validatePassword(password: string): string | null {
  if (password.length < 8) return "A senha deve ter pelo menos 8 caracteres.";
  if (!/[A-Z]/.test(password)) return "A senha deve conter pelo menos uma letra maiúscula.";
  if (!/[a-z]/.test(password)) return "A senha deve conter pelo menos uma letra minúscula.";
  if (!/\d/.test(password)) return "A senha deve conter pelo menos um número.";
  return null;
}

const emptyForm = { nome: "", email: "", password: "", setor: "GERAL", nivel_acesso: "USER", force_password_change: false };

const Admin = () => {
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // modal create/edit
  const [modal, setModal] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      setError((err as Error).message || "Erro ao carregar usuários");
    } finally {
      setLoading(false);
    }
  }

  function openCreate() {
    setForm(emptyForm);
    setFormError("");
    setEditing(null);
    setModal("create");
  }

  function openEdit(user: AdminUser) {
    setForm({ nome: user.nome, email: user.email, password: "", setor: user.setor, nivel_acesso: user.nivel_acesso, force_password_change: user.force_password_change ?? false });
    setFormError("");
    setEditing(user);
    setModal("edit");
  }

  async function toggleAtivo(user: AdminUser) {
    try {
      const updated = await updateUser(user.id, { ativo: !user.ativo });
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      alert((err as Error).message || "Erro ao atualizar usuário");
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFormError("");

    if (!form.nome.trim() || !form.email.trim()) {
      setFormError("Nome e email são obrigatórios.");
      return;
    }
    if (modal === "create") {
      const pwError = validatePassword(form.password);
      if (pwError) { setFormError(pwError); return; }
    } else if (form.password.length > 0) {
      const pwError = validatePassword(form.password);
      if (pwError) { setFormError(pwError); return; }
    }

    setSaving(true);
    try {
      if (modal === "create") {
        const created = await createUser({
          nome: form.nome,
          email: form.email,
          password: form.password,
          setor: form.setor,
          nivel_acesso: form.nivel_acesso,
          force_password_change: form.force_password_change,
        });
        setUsers((prev) => [created, ...prev]);
      } else if (editing) {
        const payload: Parameters<typeof updateUser>[1] = {
          nome: form.nome,
          setor: form.setor,
          nivel_acesso: form.nivel_acesso,
          force_password_change: form.force_password_change,
        };
        if (form.password.length > 0) payload.password = form.password;
        const updated = await updateUser(editing.id, payload);
        setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      }
      setModal(null);
    } catch (err) {
      setFormError((err as Error).message || "Erro ao salvar usuário.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="border-b border-border/60 px-6 py-4 flex items-center gap-4">
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ChevronLeft size={16} />
          Voltar
        </button>

        <div className="flex items-center gap-2.5 flex-1">
          <img src={logoVini} alt="ViniAI" className="h-7 w-7 object-contain" />
          <h1 className="text-base font-semibold tracking-tight">Gestão de Usuários</h1>
        </div>

        <button
          onClick={openCreate}
          className="flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-all hover:brightness-110"
        >
          <Plus size={15} />
          Novo usuário
        </button>
      </header>

      {/* Content */}
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {loading ? (
          <div className="flex justify-center py-20 text-sm text-muted-foreground">Carregando...</div>
        ) : error ? (
          <div className="flex flex-col items-center gap-3 py-20">
            <p className="text-sm text-red-500">{error}</p>
            <button onClick={load} className="text-sm text-foreground underline">Tentar novamente</button>
          </div>
        ) : (
          <div className="rounded-2xl border border-border/60 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-muted/40">
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">Nome</th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">Email</th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">Setor</th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">Nível</th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">Ações</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user, i) => (
                  <tr
                    key={user.id}
                    className={`border-b border-border/40 transition-colors hover:bg-muted/20 ${i % 2 === 0 ? "" : "bg-muted/10"}`}
                  >
                    <td className="px-4 py-3 font-medium">{user.nome}</td>
                    <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-lg bg-muted px-2 py-0.5 text-xs font-medium capitalize">
                        {user.setor}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-lg px-2 py-0.5 text-xs font-semibold ${
                          user.nivel_acesso === "ADMIN"
                            ? "bg-primary/15 text-primary"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {user.nivel_acesso}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => toggleAtivo(user)}
                        title={user.ativo ? "Clique para desativar" : "Clique para ativar"}
                        className={`flex items-center gap-1.5 rounded-lg px-2 py-0.5 text-xs font-semibold transition-all hover:opacity-80 ${
                          user.ativo
                            ? "bg-green-500/15 text-green-600 dark:text-green-400"
                            : "bg-red-500/15 text-red-600 dark:text-red-400"
                        }`}
                      >
                        {user.ativo ? <Check size={11} /> : <X size={11} />}
                        {user.ativo ? "Ativo" : "Inativo"}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => openEdit(user)}
                        className="flex items-center gap-1.5 rounded-lg border border-border/60 px-3 py-1.5 text-xs font-medium transition-colors hover:bg-muted"
                      >
                        <Pencil size={11} />
                        Editar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {users.length === 0 && (
              <div className="py-16 text-center text-sm text-muted-foreground">Nenhum usuário cadastrado.</div>
            )}
          </div>
        )}
      </div>

      {/* Modal */}
      {modal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4"
          onClick={(e) => { if (e.target === e.currentTarget) setModal(null); }}
        >
          <div className="w-full max-w-md rounded-2xl border border-border/70 bg-card p-7 shadow-2xl">
            <h2 className="mb-6 text-lg font-semibold tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
              {modal === "create" ? "Novo usuário" : `Editar — ${editing?.nome}`}
            </h2>

            <form onSubmit={handleSubmit} noValidate className="space-y-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">Nome</label>
                <input
                  type="text"
                  value={form.nome}
                  onChange={(e) => setForm((f) => ({ ...f, nome: e.target.value }))}
                  className="w-full rounded-xl border border-border bg-input px-4 py-2.5 text-sm outline-none focus:border-primary transition-colors"
                  placeholder="Nome completo"
                />
              </div>

              {modal === "create" && (
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                    className="w-full rounded-xl border border-border bg-input px-4 py-2.5 text-sm outline-none focus:border-primary transition-colors"
                    placeholder="email@viniplast.com.br"
                  />
                </div>
              )}

              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  {modal === "create" ? "Senha" : "Nova senha (deixe em branco para manter)"}
                </label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                  className="w-full rounded-xl border border-border bg-input px-4 py-2.5 text-sm outline-none focus:border-primary transition-colors"
                  placeholder={modal === "create" ? "Mínimo 6 caracteres" : "••••••"}
                />
              </div>

              <label className="flex items-center gap-3 cursor-pointer select-none rounded-xl border border-border px-4 py-3 transition-colors hover:bg-muted/40">
                <input
                  type="checkbox"
                  checked={form.force_password_change}
                  onChange={(e) => setForm((f) => ({ ...f, force_password_change: e.target.checked }))}
                  className="h-4 w-4 rounded accent-primary"
                />
                <span className="text-sm">Exigir troca de senha no próximo acesso</span>
              </label>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Setor</label>
                  <select
                    value={form.setor}
                    onChange={(e) => setForm((f) => ({ ...f, setor: e.target.value }))}
                    className="w-full rounded-xl border border-border bg-input px-4 py-2.5 text-sm outline-none focus:border-primary transition-colors"
                  >
                    {SETORES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">Nível</label>
                  <select
                    value={form.nivel_acesso}
                    onChange={(e) => setForm((f) => ({ ...f, nivel_acesso: e.target.value }))}
                    className="w-full rounded-xl border border-border bg-input px-4 py-2.5 text-sm outline-none focus:border-primary transition-colors"
                  >
                    {NIVEIS.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </select>
                </div>
              </div>

              {formError && (
                <p className="text-center text-sm text-red-500">{formError}</p>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setModal(null)}
                  className="flex-1 rounded-xl border border-border px-4 py-2.5 text-sm font-medium transition-colors hover:bg-muted"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="flex-1 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-all hover:brightness-110 disabled:opacity-60"
                >
                  {saving ? "Salvando..." : modal === "create" ? "Criar usuário" : "Salvar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Admin;
