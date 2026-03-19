import { useState, useRef, useEffect } from "react";
import { Send, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
}

const ChatInput = ({ onSend, disabled }: ChatInputProps) => {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
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
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 150)}px`;
    }
  }, [message]);

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div className="glass rounded-2xl overflow-hidden ">
        <div className="flex items-end gap-3 p-3">
          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Digite sua mensagem..."
              disabled={disabled}
              rows={1}
              className={cn(
                "w-full bg-transparent text-foreground placeholder:text-muted-foreground",
                "resize-none outline-none text-sm py-2 px-1",
                "max-h-[150px] min-h-[24px]",
                disabled && "opacity-50 cursor-not-allowed"
              )}
            />
          </div>

          <button
            type="submit"
            disabled={!message.trim() || disabled}
            className={cn(
              "flex-shrink-0 w-10 h-10 rounded-xl",
              "flex items-center justify-center",
              "transition-all duration-300",
              
              message.trim() && !disabled
                ? "bg-primary text-primary-foreground hover:scale-105 active:scale-95"
                : "bg-muted text-muted-foreground cursor-not-allowed"
            )}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Powered by indicator */}
      <div className="flex items-center justify-center gap-1.5 mt-3 text-xs text-muted-foreground">
        <Sparkles className="w-3 h-3" />
        <span> 2026 ViniPlast</span>
      </div>
    </form>
  );
};

export default ChatInput;
