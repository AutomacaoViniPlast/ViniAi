import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface SuggestionCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  onClick: () => void;
}

const SuggestionCard = ({ icon: Icon, title, description, onClick }: SuggestionCardProps) => {
  return (
    <button
      onClick={onClick}
      className={cn(
        "group glass rounded-xl p-5 text-left w-full",
        "transition-all duration-300",
        "hover:scale-[1.02] hover:glow",
        "gradient-border"
      )}
    >
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
          <Icon className="w-4 h-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-base font-medium text-foreground group-hover:text-primary transition-colors">
            {title}
          </h3>
          <p className="text-base text-muted-foreground mt-1 line-clamp-2">
            {description}
          </p>
        </div>
      </div>
    </button>
  );
};

export default SuggestionCard;
