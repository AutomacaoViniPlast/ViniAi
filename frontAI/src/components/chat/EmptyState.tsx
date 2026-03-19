import { Code, Lightbulb, MessageSquare, Palette } from "lucide-react";
import SuggestionCard from "./SuggestionCard";
import { Description } from "@radix-ui/react-toast";

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
      icon: Lightbulb,
      title: "Produção total por mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: Code,
      title: "Produção em um dia específico",
      description: "Quanto nós produzimos no dia 2025-12-04 ?",
    },
  ],

   CEO: [
    {
      icon: Lightbulb,
      title: "Perda média por família",
      description: "Qual foi a perda média das famílias G32 e K37 no mês de setembro de 2024?",
    },
    {
      icon: Code,
      title: "Produção total do mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: Palette,
      title: "Último registro de Ordem de Produção",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: MessageSquare,
      title: "Maior volume em KG do mês",
      description: "Qual foi a condição que teve o maior volume de quilos em agosto de 2024 e qual era o percentual de perda dela?",
    }
  ],

  DIRETORIA: [
    {
      icon: Lightbulb,
      title: "Perda média por família",
      description: "Qual foi a perda média das famílias G32 e K37 no mês de setembro de 2024?",
    },
    {
      icon: Code,
      title: "Produção total do mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: Palette,
      title: "Último registro de Ordem de Produção",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: MessageSquare,
      title: "Maior volume em KG do mês",
      description: "Qual foi a condição que teve o maior volume de quilos em agosto de 2024 e qual era o percentual de perda dela?",
    }
  ],

    DESENVOLVEDOR: [
    {
      icon: Lightbulb,
      title: "Perda média por família",
      description: "Qual foi a perda média das famílias G32 e K37 no mês de setembro de 2024?",
    },
    {
      icon: Code,
      title: "Produção total do mês",
      description: "Qual foi a produção total do mês de dezembro de 2025 ?",
    },
    {
      icon: Palette,
      title: "Último registro de Ordem de Produção",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: MessageSquare,
      title: "Maior volume em KG do mês",
      description: "Qual foi a condição que teve o maior volume de quilos em agosto de 2024 e qual era o percentual de perda dela?",
    }
  ],


  PCP: [
    {
      icon: Lightbulb,
      title: "Última OP registrada",
      description: "Qual foi a última OP registrada no sistema?",
    },
    {
      icon: Code,
      title: "Status da produção",
      description: "Qual o status atual da produção?",
    },
    {
      icon: Palette,
      title: "Produção do mês",
      description: "Qual foi a produção total deste mês?",
    },
    {
      icon: MessageSquare,
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
    <div className="flex-1 flex flex-col items-center justify-center px-4 animate-fade-in overflow-hidden">

      <div className="relative mb-10 top-5">
        <div className="w-20 h-20 rounded-2xl glass gradient-border flex items-center justify-center glow animate-float">
          <span className="text-1xl font-display font-bold gradient-text">
            ViniAI
          </span>
        </div>

        <div className="absolute -top-4 -right-4 w-8 h-8 rounded-full bg-primary/20 blur-sm animate-pulse-slow" />
        <div className="absolute -bottom-2 -left-4 w-6 h-6 rounded-full bg-secondary/30 blur-sm animate-pulse-slow" />
      </div>

      <div className="flex flex-col items-center w-full">

        <h1 className="text-2xl md:text-3xl font-display font-bold text-center mb-3">
          Como posso ajudar <span className="gradient-text">hoje?</span>
        </h1>

        <p className="text-muted-foreground text-center text-base max-w-md mb-5">
          Pergunte qualquer coisa. Estou aqui para ajudar com o que eu puder.
        </p>

        <div className="hidden sm:grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-5xl">
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
    </div>
  );
};

export default EmptyState;