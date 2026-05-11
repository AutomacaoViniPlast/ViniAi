import React from "react";
import { cn } from "@/lib/utils";
import { Bot, User } from "lucide-react";
import { useTypewriter } from "../../hooks/useTypewriter";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

interface ChatMessageProps {
  id: string;
  content: string;
  role: "user" | "assistant";
  isTyping?: boolean;
  userPhoto?: string;
}

const ChatMessage = ({
  id,
  content,
  role,
  isTyping,
  userPhoto,
}: ChatMessageProps) => {
  const isUser = role === "user";

  const shouldAnimate = role === "assistant" && !isTyping;

  const { displayed } = useTypewriter(
    id,
    shouldAnimate ? content : content,
    8
  );

  return (
    <div
      className={cn(
        "flex gap-4",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <div
        className={cn(
          "w-8 h-8 flex items-center justify-center shrink-0 rounded-full overflow-hidden",
          isUser ? "text-primary" : "text-foreground"
        )}
      >
        {isUser ? (
          userPhoto ? (
            <img src={userPhoto} alt="Perfil" className="w-full h-full object-cover" />
          ) : (
            <User size={20} strokeWidth={2.5} />
          )
        ) : (
          <Bot size={20} strokeWidth={2.5} />
        )}
      </div>

      <div
        className={cn(
          "max-w-[85%] sm:max-w-[75%] px-5 py-3 rounded-2xl shadow-sm",
          isUser
            ? "bg-primary text-white rounded-tr-[4px]"
            : "bg-secondary/50 backdrop-blur-md rounded-tl-[4px]"
        )}
      >
        {isTyping ? (
          <div className="flex items-center gap-1.5 text-muted-foreground font-medium py-1">
            <span className="animate-pulse">Pensando</span>
          </div>
        ) : (
          <div className={cn("max-w-none break-words", isUser ? "text-white [&_*]:!text-white" : "prose-chat")}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
              components={{
                table: ({ children }) => (
                  <div className="w-full overflow-x-auto my-4 scrollbar-thin scrollbar-thumb-border">
                    <table className="min-w-full border-collapse">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => <th className="px-4 py-2 border border-border/50 bg-muted/50 text-left font-semibold">{children}</th>,
                td: ({ children }) => <td className="px-4 py-2 border border-border/50">{children}</td>,
              }}
            >
              {displayed}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
};

export default React.memo(ChatMessage);