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
      className="text-left w-full rounded-2xl p-4 transition-all duration-200 animate-scale-in"
      style={{
        background: hovered ? "hsl(220 25% 14%)" : "#0b0f1aff",
        border: hovered
          ? "1px solid hsl(4 82% 47% / 0.4)"
          : "1px solid hsl(220 15% 16%)",
        boxShadow: hovered ? "0 4px 20px hsl(4 82% 47% / 0.1)" : "none",
        transform: hovered ? "translateY(-2px)" : "translateY(0)",
      }}
    >
      <div className="flex items-start gap-3">
        {/* Ícone */}
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition-all duration-200"
          style={{
            background: hovered ? "hsl(4 82% 47% / 0.18)" : "hsl(214 60% 20% / 0.5)",
            border: hovered ? "1px solid hsl(4 82% 47% / 0.35)" : "1px solid hsl(214 60% 25% / 0.3)",
          }}
        >
          <Icon
            size={16}
            style={{ color: hovered ? "hsl(4 82% 62%)" : "hsla(246, 10%, 64%, 1.00)" }}
            strokeWidth={2}
          />
        </div>

        {/* Texto */}
        <div className="flex-1 min-w-0">
          <h3
            className="text-sm font-semibold mb-1 transition-colors duration-200"
            style={{ color: hovered ? "hsl(0 0% 98%)" : "hsl(0 0% 88%)" }}
          >
            {title}
          </h3>
          <p
            className="text-xs leading-relaxed line-clamp-2 transition-colors duration-200"
            style={{ color: "hsla(215, 19%, 67%, 1.00)" }}
          >
            {description}
          </p>
        </div>
      </div>
    </button>
  );
};

export default SuggestionCard;
