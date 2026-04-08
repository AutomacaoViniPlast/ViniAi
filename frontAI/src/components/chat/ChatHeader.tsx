import { Menu, Plus, Settings } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatHeaderProps {
  onNewChat?: () => void;
}

const ChatHeader = ({ onNewChat }: ChatHeaderProps) => {
  return (
    <header className="glass border-b border-border/50 px-4 py-3">
      <div className="flex items-center justify-between max-w-4xl mx-auto">
        {/* Left side */}
        <div className="flex items-center gap-3">
          <button className="w-9 h-9 rounded-lg hover:bg-muted/50 flex items-center justify-center transition-colors md:hidden">
            <Menu className="w-5 h-5 text-muted-foreground" />
          </button>

          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <span className="text-sm font-display font-bold gradient-text">AI</span>
            </div>
            <div className="hidden sm:block">
              <h1 className="text-sm font-semibold">Conversa Atual</h1>
              <p className="text-xs text-muted-foreground">Modelo gpt-4o-mini</p>
            </div>
          </div>
        </div>

        {/* Right side */}
        <div className="flex items-center gap-2">
          <button
            onClick={onNewChat}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-lg",
              "bg-primary/10 hover:bg-primary/20 text-primary",
              "transition-all duration-200 text-sm font-medium"
            )}
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Nova</span>
          </button>

          <button className="w-9 h-9 rounded-lg hover:bg-muted/50 flex items-center justify-center transition-colors">
            <Settings className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default ChatHeader;
