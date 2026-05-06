import { LucideIcon } from "lucide-react";
import { useState } from "react";

interface SuggestionCardProps {
  icon: LucideIcon;
  title: string;
  description: string;
  onClick: () => void;
}

const SuggestionCard = ({ icon: Icon, title, description, onClick }: SuggestionCardProps) => {
  const [hovered, setHovered] = useState(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className="text-left w-full rounded-2xl p-4 outline-none select-none active:scale-[0.98]"
      style={{
        background: hovered ? "hsl(var(--secondary))" : "hsl(var(--card))",
        border: hovered
          ? "1px solid hsl(var(--primary))"
          : "1px solid transparent",
        boxShadow: "none",
        transform: hovered ? "translateY(-2px)" : "translateY(0)",
        transition: "background 0.2s ease, border 0.2s ease, transform 0.2s ease",
      }}
    >
      <div className="flex items-start gap-3">
        {/* Ícone */}
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200"
          style={{
            background: hovered ? "hsl(var(--primary) / 0.18)" : "hsl(var(--muted))",
            border: hovered ? "1px solid hsl(var(--primary) / 0.35)" : "1px solid transparent",
          }}
        >
          <Icon
            size={16}
            style={{ color: hovered ? "hsl(var(--primary))" : "hsl(var(--muted-foreground))" }}
            strokeWidth={2}
          />
        </div>

        {/* Texto */}
        <div className="flex-1 min-w-0">
          <h3
            className="text-sm font-semibold mb-1 transition-colors duration-200"
            style={{ color: hovered ? "hsl(var(--foreground))" : "hsl(var(--foreground) / 0.85)" }}
          >
            {title}
          </h3>
          <p
            className="text-xs leading-relaxed line-clamp-2 transition-colors duration-200"
            style={{ color: "hsl(var(--muted-foreground))" }}
          >
            {description}
          </p>
        </div>
      </div>
    </button>
  );
};

export default SuggestionCard;
