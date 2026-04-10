import { Code, Lightbulb, MessageSquare, Palette, TrendingUp, BarChart2, ClipboardList, Factory } from "lucide-react";
import SuggestionCard from "./SuggestionCard";
import logoVini from "../../image/logoviniai2.png";

interface EmptyStateProps {
  onSuggestionClick: (text: string) => void;
  setor?: string;
}

const sectorSuggestions = {
  GERAL: [
    {
      icon: Lightbulb,
      title: "Sobre a empresa",
      description: "Me apresente a ViniPlast",
    },
    {
      icon: Code,
      title: "Produtos em catálogo",
      description: "Me apresente os produtos disponíveis em catálogo",
    },
    {
      icon: Palette,
      title: "Orçamentos e Medidas",
      description: "Me dê um orçamento resumido de cada produto",
    },
    {
      icon: MessageSquare,
      title: "Falar com atendente humano",
      description: "Eu gostaria de falar com um atendente humano",
    },
  ],

  CONTROLADORIA: [
    {
      icon: Lightbulb,
      title: "Perda média por família",
      description: "Qual foi a perda média das famílias G32 e K37 no mês de setembro de 2024?",
    },
    {
      icon: Code,
      title: "Metros totais de material Inteiro",
      description: "Somando os meses de agosto e setembro de 2024, qual o total de material INTEIRO produzido?",
    },
    {
      icon: Palette,
      title: "Maior volume em KG do mês",
      description: "Qual foi a condição que teve o maior volume de quilos em agosto de 2024 e qual era o percentual de perda dela?",
    },
    {
      icon: MessageSquare,
      title: "Perda por Condição",
      description: "Verifique na tabela BAG: qual foi a perda da condição LD em agosto de 2024?",
    },
  ],

  PRODUÇÃO: [
    {
      icon: Factory,
      title: "Produção total por mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: ClipboardList,
      title: "Produção em um dia específico",
      description: "Quanto nós produzimos no dia 2025-12-04 ?",
    },
  ],

  CEO: [
    {
      icon: TrendingUp,
      title: "Perda média por família",
      description: "Qual foi a perda média das famílias G32 e K37 no mês de setembro de 2024?",
    },
    {
      icon: BarChart2,
      title: "Produção total do mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: ClipboardList,
      title: "Último registro de Ordem de Produção",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: Lightbulb,
      title: "Maior volume em KG do mês",
      description: "Qual foi a condição que teve o maior volume de quilos em agosto de 2024 e qual era o percentual de perda dela?",
    }
  ],

  DIRETORIA: [
    {
      icon: TrendingUp,
      title: "Perda média por família",
      description: "Qual foi a perda média das famílias G32 e K37 no mês de setembro de 2024?",
    },
    {
      icon: BarChart2,
      title: "Produção total do mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: ClipboardList,
      title: "Último registro de Ordem de Produção",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: Lightbulb,
      title: "Maior volume em KG do mês",
      description: "Qual foi a condição que teve o maior volume de quilos em agosto de 2024 e qual era o percentual de perda dela?",
    }
  ],

  DESENVOLVEDOR: [
    {
      icon: TrendingUp,
      title: "Perda média por família",
      description: "Qual foi a perda média das famílias G32 e K37 no mês de setembro de 2024?",
    },
    {
      icon: BarChart2,
      title: "Produção total do mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: ClipboardList,
      title: "Último registro de Ordem de Produção",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: Lightbulb,
      title: "Maior volume em KG do mês",
      description: "Qual foi a condição que teve o maior volume de quilos em agosto de 2024 e qual era o percentual de perda dela?",
    }
  ],

  PCP: [
    {
      icon: ClipboardList,
      title: "Última OP registrada",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: BarChart2,
      title: "Status da produção",
      description: "Qual o status atual da produção?",
    },
    {
      icon: Factory,
      title: "Produção do mês",
      description: "Qual foi a produção total deste mês?",
    },
    {
      icon: Code,
      title: "Consumo por OP",
      description: "Me mostre o consumo de matéria-prima por OP",
    },
  ],
};

const EmptyState = ({ onSuggestionClick, setor }: EmptyStateProps) => {
  const suggestions =
    sectorSuggestions[setor as keyof typeof sectorSuggestions] ||
    sectorSuggestions.GERAL;

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 pt-2 pb-16 md:pb-12 animate-fade-in overflow-y-auto">

      {/* Logo da imagem */}
      <div className="flex justify-center items-center mt-6 mb-2 animate-float">
        <img
          src={logoVini}
          alt="ViniAI Logo"
          className="w-40 md:w-36 h-auto max-h-15"
        />
      </div>

      {/* Título */}
      <div className="text-center mb-2">
        <h1
          className="text-3xl md:text-4xl font-bold mb-3"
          style={{ fontFamily: "'Space Grotesk', sans-serif", color: "hsl(0 0% 95%)", letterSpacing: "-0.02em" }}
        >
          Como posso{" "}
          <span
            style={{
              background: "linear-gradient(135deg, hsla(4, 100%, 50%, 1.00), hsla(4, 84%, 63%, 1.00))",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            ajudar hoje?
          </span>
        </h1>
        <p className="text-base max-w-md mx-auto" style={{ color: "hsl(215 15% 58%)" }}>
          Faça uma pergunta ou escolha uma das sugestões abaixo para começar.
        </p>
      </div>

      {/* Cards de sugestão */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 w-full max-w-4xl mt-6">
        {suggestions.map((suggestion, index) => (
          <SuggestionCard
            key={index}
            icon={suggestion.icon}
            title={suggestion.title}
            description={suggestion.description}
            onClick={() => onSuggestionClick(suggestion.description)}
          />
        ))}
      </div>

    </div>
  );
};

export default EmptyState;