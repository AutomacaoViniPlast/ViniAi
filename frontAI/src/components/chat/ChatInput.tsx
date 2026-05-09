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
        className="rounded-3xl overflow-hidden outline-none relative"
        style={{
          background: "hsl(var(--input))",
          border: focused ? "1px solid hsl(var(--foreground) / 0.03)" : "1px solid transparent",
          boxShadow: "none",
          transition: "all 0.3s ease",
        }}
      >
        <div className="flex items-end px-5 py-3">
          {/* Textarea */}
          <div className="flex-1 pr-10">
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
                caretColor: "hsl(var(--foreground))",
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
            className={`absolute right-4 bottom-3 shrink-0 w-9 h-9 rounded-xl flex items-center justify-center transition-all duration-500 bg-primary text-white hover:brightness-110 hover:scale-110 active:scale-95 ${
              canSend ? "opacity-100 scale-100" : "opacity-0 scale-0 pointer-events-none"
            }`}
            style={{ transitionTimingFunction: "cubic-bezier(0.34, 1.56, 0.64, 1)" }}
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
