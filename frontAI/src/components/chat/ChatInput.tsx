import { useState, useRef, useEffect } from "react";
import { ArrowUp, Sparkles } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

const ChatInput = ({ onSend, disabled }: ChatInputProps) => {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [focused, setFocused] = useState(false);

  const canSend = message.trim() && !disabled;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (canSend) {
      onSend(message.trim());
      setMessage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [message]);

  return (
    <form onSubmit={handleSubmit}>
      <div
        className="rounded-3xl overflow-hidden transition-all duration-200"
        style={{
          background: "hsl(var(--input))",
          border: focused
            ? "1px solid hsl(var(--primary) / 0.5)"
            : "1px solid hsl(var(--border))",
        }}
      >
        <div className="flex items-end gap-4 px-5 py-3">
          {/* Textarea */}
          <div className="flex-1  ">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              placeholder="Digite sua mensagem..."
              disabled={disabled}
              rows={1}
              className="w-full bg-transparent text-base outline-none resize-none pt-1.5"
              style={{
                color: "hsl(var(--foreground))",
                caretColor: "hsl(4 82% 55%)",
                maxHeight: "200px",
                minHeight: "24px",
                lineHeight: "1.6",
                opacity: disabled ? 0.5 : 1,
                cursor: disabled ? "not-allowed" : "text",
              }}
            />
            <style>{`
              textarea::placeholder { color: hsl(var(--muted-foreground) / 0.7); }
            `}</style>
          </div>

          {/* Botão enviar */}
          <button
            type="submit"
            disabled={!canSend}
            className="shrink-0 w-9 h-9 self-center rounded-xl flex items-center justify-center transition-all duration-200"
            style={{
              background: canSend ? "#ad1e13ff" : "hsl(var(--muted))",
              color: canSend ? "#fff" : "hsl(var(--muted-foreground))",
              cursor: canSend ? "pointer" : "not-allowed",
              transform: "scale(1)",
            }}
            onMouseEnter={e => {
              if (canSend) {
                (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.08)";
                (e.currentTarget as HTMLButtonElement).style.background = "hsl(4 82% 40%)";
              }
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)";
              (e.currentTarget as HTMLButtonElement).style.background = canSend ? "hsl(4 82% 47%)" : "hsl(var(--muted))";
            }}
          >
            <ArrowUp size={16} strokeWidth={2.5} />
          </button>
        </div>
      </div>

      {/* Rodapé */}
      <div className="flex items-center justify-center gap-1.5 mt-2.5">
        <Sparkles size={11} style={{ color: "hsl(var(--muted-foreground) / 0.6)" }} />
        <span className="text-xs" style={{ color: "hsl(var(--muted-foreground) / 0.6)" }}>
          &copy; 2026 VINIPLAST. Todos os direitos reservados.
        </span>
      </div>
    </form>
  );
};

export default ChatInput;
