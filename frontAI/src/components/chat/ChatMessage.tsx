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
}

const ChatMessage = ({
  id,
  content,
  role,
  isTyping,
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
          "w-10 h-10 rounded-xl flex items-center justify-center",
          isUser
            ? "bg-primary/20 text-primary"
            : "glass"
        )}
      >
        {isUser ? <User size={18} /> : <Bot size={18} />}
      </div>

      <div
        className={cn(
          "max-w-[75%] px-5 py-3.5 rounded-2xl",
          isUser
            ? "bg-primary text-primary-foreground rounded-br-md"
            : "glass rounded-bl-md"
        )}
      >
        {isTyping ? (
          <div className="flex gap-1">
            <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce" />
            <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-100" />
            <span className="w-2 h-2 bg-muted-foreground rounded-full animate-bounce delay-200" />
          </div>
        ) : (
          <div className="prose-chat max-w-none break-words">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
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