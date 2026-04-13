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
          background: "#080b14ff",
          border: "1px solid #1b1e25ff",
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
              placeholder="Escreva sua mensagem..."
              disabled={disabled}
              rows={1}
              className="w-full bg-transparent text-base outline-none resize-none pt-1.5"
              style={{
                color: "hsl(0 0% 92%)",
                caretColor: "hsl(4 82% 55%)",
                maxHeight: "200px",
                minHeight: "24px",
                lineHeight: "1.6",
                opacity: disabled ? 0.5 : 1,
                cursor: disabled ? "not-allowed" : "text",
              }}
            />
            <style>{`
              textarea::placeholder { color: hsl(215 15% 45%); }
            `}</style>
          </div>

          {/* Botão enviar */}
          <button
            type="submit"
            disabled={!canSend}
            className="shrink-0 w-9 h-9 self-center rounded-xl flex items-center justify-center transition-all duration-200"
            style={{
              background: canSend ? "#ad1e13ff" : "hsl(220 20% 17%)",
              color: canSend ? "#fff" : "hsl(215 15% 45%)",
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
              (e.currentTarget as HTMLButtonElement).style.background = canSend ? "hsl(4 82% 47%)" : "hsl(220 20% 17%)";
            }}
          >
            <ArrowUp size={16} strokeWidth={2.5} />
          </button>
        </div>
      </div>

      {/* Rodapé */}
      <div className="flex items-center justify-center gap-1.5 mt-2.5">
        <Sparkles size={11} style={{ color: "hsl(215 15% 40%)" }} />
        <span className="text-xs" style={{ color: "hsl(215 15% 40%)" }}>
          ViniPlast © 2026
        </span>
      </div>
    </form>
  );
};

export default ChatInput;
