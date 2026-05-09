import React, { useState, useRef } from "react";
import { X, Camera, Save, Shield, Trash2 } from "lucide-react";
import { toast } from "sonner";

interface ProfileEditProps {
  user: {
    nome: string;
    setor: string;
    nivel_acesso?: string;
    photo?: string;
  } | null;
  onClose: () => void;
  onSave?: (data: { nome: string; setor: string; photo?: string | null }) => void;
}

const ProfileEdit = ({ user, onClose, onSave }: ProfileEditProps) => {
  const [nome, setNome] = useState(user?.nome || "");
  const [setor] = useState(user?.setor || "");
  const [profilePhoto, setProfilePhoto] = useState<string | null>(user?.photo || null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const initials = user?.nome
    ? user.nome
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : "AI";

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.type.startsWith("image/")) {
        toast.error("Por favor, selecione apenas arquivos de imagem.");
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        setProfilePhoto(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (onSave) onSave({ nome, setor, photo: profilePhoto });
    onClose();
  };

  return (
    <div
      className="flex-1 flex flex-col h-full animate-in fade-in duration-300 overflow-y-auto"
      style={{ background: "var(--app-bg)" }}
    >
      <div className="flex-1 flex flex-col items-center justify-center p-4 md:p-8">
        <div className="w-full max-w-2xl bg-card rounded-[2.5rem] overflow-hidden relative">
          {/* Cabeçalho */}
          <div className="relative h-28 bg-white/[0.02] overflow-hidden">
            <div
              className="absolute inset-0 opacity-[0.03]"
              style={{
                backgroundImage:
                  "radial-gradient(circle at 2px 2px, currentColor 1px, transparent 0)",
                backgroundSize: "24px 24px",
              }}
            />
            <div className="absolute inset-0 bg-gradient-to-b from-transparent to-card" />
            <button
              onClick={onClose}
              className="absolute top-6 right-6 w-10 h-10 rounded-full flex items-center justify-center bg-background/50 text-foreground/50 hover:text-foreground transition-all duration-200 z-10"
            >
              <X size={20} />
            </button>
          </div>

          <div className="px-8 pb-10 -mt-14 relative z-10">
            <div className="flex flex-col items-center">
              {/* Foto de perfil */}
              <div className="relative group">
                <div className="absolute -inset-1.5 rounded-full border border-white/10" />
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept="image/*"
                  className="hidden"
                />
                <div
                  className="w-28 h-28 rounded-full flex items-center justify-center text-3xl font-bold text-white shrink-0 border-4 border-card relative z-10 overflow-hidden group/avatar"
                  style={{ background: profilePhoto ? "transparent" : "hsl(var(--primary))" }}
                >
                  {profilePhoto ? (
                    <>
                      <img src={profilePhoto} alt="Perfil" className="w-full h-full object-cover" />
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setProfilePhoto(null);
                        }}
                        className="absolute inset-0 bg-black/60 flex items-center justify-center opacity-0 group-hover/avatar:opacity-100 transition-opacity duration-200"
                        title="Remover foto"
                      >
                        <Trash2 size={24} className="text-white" />
                      </button>
                    </>
                  ) : (
                    initials
                  )}
                </div>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="absolute bottom-0 right-0 w-9 h-9 rounded-full bg-primary text-white flex items-center justify-center border-4 border-card transition-transform duration-200 z-20 hover:scale-110 active:scale-95"
                >
                  <Camera size={16} />
                </button>
              </div>

              <div className="mt-6 text-center">
                <h2 className="text-xl font-bold text-foreground">Editar Perfil</h2>
                <p className="text-muted-foreground text-sm">Personalize suas informações na ViniAI</p>
              </div>

              {/* Formulário */}
              <form onSubmit={handleSave} className="w-full mt-8 space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 px-1">
                      Nome Completo
                    </label>
                    <input
                      type="text"
                      value={nome}
                      onChange={(e) => setNome(e.target.value)}
                      className="w-full rounded-2xl border-none bg-white/5 px-6 py-4 text-sm font-medium outline-none transition-all duration-300 focus:bg-white/10 focus:scale-[1.01]"
                      placeholder="Seu nome"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground/60 px-1">
                      Setor / Departamento
                    </label>
                    <input
                      type="text"
                      value={setor}
                      readOnly
                      className="w-full rounded-2xl border-none bg-white/[0.02] px-6 py-4 text-sm font-medium outline-none cursor-default opacity-50"
                    />
                  </div>
                </div>

                <div className="p-4 rounded-3xl bg-primary/[0.04] flex items-center gap-4">
                  <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center text-white shrink-0">
                    <Shield size={20} />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-primary/60 leading-none mb-1">
                      Status da Conta
                    </p>
                    <p className="text-sm font-bold text-foreground flex items-center gap-2">
                      Acesso <span className="text-primary">{user?.nivel_acesso || "USUÁRIO"}</span>
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-4 pt-4">
                  <button
                    type="button"
                    onClick={onClose}
                    className="flex-1 py-4 rounded-2xl font-bold text-xs uppercase tracking-widest transition-all duration-200 hover:bg-white/5 text-muted-foreground"
                  >
                    Voltar
                  </button>
                  <button
                    type="submit"
                    className="flex-[2] py-4 rounded-2xl bg-primary text-white font-bold text-xs uppercase tracking-widest hover:scale-[1.01] active:scale-[0.99] transition-all duration-300 flex items-center justify-center gap-2"
                  >
                    <Save size={16} /> Salvar
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfileEdit;
