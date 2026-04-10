"""
interpreter.py — Interpretador de intenções baseado em regras (sem LLM).

Analisa o texto do usuário e classifica a mensagem em uma intenção e rota,
sem depender de chamadas externas — determinístico, rápido e sem custo de API.

Como funciona:
  1. Testa padrões de regex em ordem de prioridade.
  2. Extrai entidades: período, operador, produto, setor, origem, top_n.
  3. Retorna InterpretationResult com intent, route e confiança.

Rotas possíveis:
  sql       → consulta ao banco de dados (SQLService)
  smalltalk → conversa natural (LLMHandler / ChatGPT)
  clarify   → não entendeu — ChatGPT responde com orientação natural

Para adicionar novos padrões: inclua novos atributos de regex na classe
RuleBasedInterpreter e adicione a verificação em ordem no método interpret().
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from app.config import ORIGENS, SETORES, _normalizar_setor, todos_operadores
from app.schemas import InterpretationResult

# ── Meses PT-BR ───────────────────────────────────────────────────────────────
MESES: dict[str, int] = {
    "janeiro": 1,  "jan": 1,
    "fevereiro": 2, "fev": 2,
    "março": 3, "marco": 3, "mar": 3,
    "abril": 4,  "abr": 4,
    "maio": 5,   "mai": 5,
    "junho": 6,  "jun": 6,
    "julho": 7,  "jul": 7,
    "agosto": 8, "ago": 8,
    "setembro": 9,  "set": 9,
    "outubro": 10,  "out": 10,
    "novembro": 11, "nov": 11,
    "dezembro": 12, "dez": 12,
}

# ── Patterns compilados ───────────────────────────────────────────────────────
_RE_MONTH_YEAR = re.compile(
    r"\b(" + "|".join(sorted(MESES, key=len, reverse=True)) + r")\b"
    r"(?:\s+de\s+|\s+)?"
    r"(20\d{2})?",
    re.IGNORECASE,
)
_RE_YEAR_ONLY  = re.compile(r"\b(20\d{2})\b")
_RE_TOP_N      = re.compile(r"\btop\s*(\d+)\b", re.IGNORECASE)
_RE_OPERATOR   = re.compile(r"\b([a-záéíóúâêîôûãõç]+\.[a-záéíóúâêîôûãõç]+)\b", re.IGNORECASE)
_RE_MES_PASS   = re.compile(r"m[eê]s\s+passado", re.IGNORECASE)
_RE_MES_ATUAL  = re.compile(r"este\s+m[eê]s|m[eê]s\s+atual", re.IGNORECASE)
_RE_ANO_PASS   = re.compile(r"ano\s+passado", re.IGNORECASE)
_RE_ANO_ATUAL  = re.compile(r"este\s+ano|ano\s+atual", re.IGNORECASE)
_RE_PRODUTO    = re.compile(r"\b(TD2[A-Z0-9]{2,})\b", re.IGNORECASE)


def _periodo_from_text(text: str) -> tuple[str | None, str | None, str | None]:
    """
    Extrai (data_inicio, data_fim, period_label) a partir de texto livre.
    Retorna strings no formato DD/MM/YYYY.
    """
    today = date.today()
    lowered = text.lower()

    # "mês passado"
    if _RE_MES_PASS.search(lowered):
        primeiro = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        ultimo_dia = calendar.monthrange(primeiro.year, primeiro.month)[1]
        ultimo = primeiro.replace(day=ultimo_dia)
        return (
            primeiro.strftime("%d/%m/%Y"),
            ultimo.strftime("%d/%m/%Y"),
            f"{_mes_nome(primeiro.month)} de {primeiro.year}",
        )

    # "este mês / mês atual"
    if _RE_MES_ATUAL.search(lowered):
        primeiro = today.replace(day=1)
        ultimo_dia = calendar.monthrange(today.year, today.month)[1]
        ultimo = today.replace(day=ultimo_dia)
        return (
            primeiro.strftime("%d/%m/%Y"),
            ultimo.strftime("%d/%m/%Y"),
            f"{_mes_nome(today.month)} de {today.year}",
        )

    # "ano passado"
    if _RE_ANO_PASS.search(lowered):
        ano = today.year - 1
        return f"01/01/{ano}", f"31/12/{ano}", str(ano)

    # "este ano / ano atual"
    if _RE_ANO_ATUAL.search(lowered):
        ano = today.year
        return f"01/01/{ano}", f"31/12/{ano}", str(ano)

    # "janeiro de 2026" / "janeiro 2026" / "em janeiro"
    m = _RE_MONTH_YEAR.search(lowered)
    if m:
        mes_str = m.group(1).lower()
        ano_str = m.group(2)
        mes = MESES[mes_str]
        ano = int(ano_str) if ano_str else today.year
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        return (
            f"01/{mes:02d}/{ano}",
            f"{ultimo_dia:02d}/{mes:02d}/{ano}",
            f"{_mes_nome(mes)} de {ano}",
        )

    # só ano: "em 2025"
    m2 = _RE_YEAR_ONLY.search(text)
    if m2:
        ano = int(m2.group(1))
        return f"01/01/{ano}", f"31/12/{ano}", str(ano)

    return None, None, None


def _mes_nome(mes: int) -> str:
    return list(MESES.keys())[list(MESES.values()).index(mes)].capitalize()


class RuleBasedInterpreter:
    """
    Interpretador baseado em regras para o setor de Produção.
    Cobre: LD, produção total, rankings, produtos, turnos, comparações.
    """

    # ── Agrupamentos de palavras-chave ────────────────────────────────────────
    _LD       = re.compile(r"\bld\b", re.IGNORECASE)
    _GERACAO  = re.compile(r"gera[cç][aã]o|gerou|gerada|geradas", re.IGNORECASE)
    _PRODUCAO = re.compile(r"produ[cç][aã]o|produziu|produzido|produzidos", re.IGNORECASE)
    _RANKING  = re.compile(r"ranking|classifica[cç][aã]o|quem mais|mais produziu|maior produt", re.IGNORECASE)
    _TOP      = re.compile(r"\btop\b", re.IGNORECASE)
    _PRODUTO  = re.compile(r"produto|material|referencia|referência|código|codigo", re.IGNORECASE)
    _TURNO    = re.compile(r"\bturno\b", re.IGNORECASE)
    _TOTAL    = re.compile(r"\btotal\b|\bfábrica\b|\bfabrica\b|\bgeral\b", re.IGNORECASE)
    _OPERADOR = re.compile(r"operador(?:es)?|revis[aã]o", re.IGNORECASE)
    _QUEM     = re.compile(r"\bquem\b", re.IGNORECASE)
    _QUAL     = re.compile(r"\bqual\b", re.IGNORECASE)
    _LISTA    = re.compile(r"list[ae]|mostre|exib[ae]|quais|s[aã]o os|da revis[aã]o|da expedi[cç][aã]o|da produ[cç][aã]o", re.IGNORECASE)
    _SMALLTALK = re.compile(
        r"^(oi|ol[aá]|bom\s+dia|boa\s+tarde|boa\s+noite|"
        r"tudo\s+bem|tudo\s+bom|tudo\s+certo|e\s+a[ií]|"
        r"como\s+vai|como\s+voc[eê]\s+est[aá]|"
        r"obrigad[ao]|valeu|show|bl[zZ]|beleza|"
        r"oi\s+tudo|preciso\s+de\s+ajuda|pode\s+me\s+ajudar|"
        r"boa\b|ol[aá]\s+boa|e\s+a[ií]\s+boa)\b",
        re.IGNORECASE,
    )
    _SMALLTALK_LONGA = re.compile(
        r"(como\s+voc[eê]\s+est[aá]|como\s+vai\s+voc[eê]|"
        r"o\s+que\s+[eé]\s+ld|me\s+conta\s+sobre|"
        r"me\s+explica|conta\s+pra\s+mim|"
        r"quero\s+entender|n[aã]o\s+entendi|"
        r"boa\s+noite\s+vin|oi\s+vin|ol[aá]\s+vin)",
        re.IGNORECASE,
    )
    _COMPARA  = re.compile(r"compar[ae]|diferen[cç]a|versus|vs\.?|contra", re.IGNORECASE)
    _CAPACIDADES = re.compile(
        r"tipos?\s+de\s+informa[cç][aã]o|o\s+que\s+voc[eê]?\s+sabe|o\s+que\s+conseg|"
        r"quais?\s+informa[cç][oõ]es|o\s+que\s+pod[eê]|capacidade|funcionalidade|"
        r"o\s+que\s+.{0,20}informa|como\s+usar|o\s+que\s+faz",
        re.IGNORECASE,
    )
    _PERIODOS = re.compile(
        r"quais?\s+m[eê]ses?|quais?\s+anos?|per[ií]odos?\s+dispon[ií]veis?|"
        r"desde\s+quando|at[eé]\s+quando|qual\s+(?:o\s+)?per[ií]odo|"
        r"quais?\s+dados?\s+(?:tem|tenho|temos|dispon[ií]veis?)|"
        r"de\s+quando\s+[aà]\s+quando",
        re.IGNORECASE,
    )

    def interpret(self, message: str) -> InterpretationResult:
        text = message.strip()
        low  = text.lower()

        # ── 1. Capacidades / o que a IA sabe fazer ───────────────────────────
        if self._CAPACIDADES.search(low):
            return InterpretationResult(
                intent="tipos_informacao", route="smalltalk",
                confidence=0.95, reasoning="Pergunta sobre capacidades da IA.",
            )

        # ── 2. Períodos disponíveis no banco ──────────────────────────────────
        if self._PERIODOS.search(low):
            return InterpretationResult(
                intent="periodos_disponiveis", route="sql",
                confidence=0.93, reasoning="Pergunta sobre cobertura temporal dos dados.",
            )

        # ── 3. Saudação / conversa natural ───────────────────────────────────
        if self._SMALLTALK.search(low) and len(text.split()) <= 8:
            return InterpretationResult(
                intent="smalltalk", route="smalltalk",
                confidence=0.98, reasoning="Saudação identificada.",
            )
        if self._SMALLTALK_LONGA.search(low):
            return InterpretationResult(
                intent="smalltalk", route="smalltalk",
                confidence=0.90, reasoning="Conversa natural identificada.",
            )

        # Extração comum
        data_inicio, data_fim, period_text = _periodo_from_text(text)
        top_n    = self._extract_top_n(text)
        operador = self._extract_operator(text)
        produto  = self._extract_produto_code(text)
        setor    = self._extract_setor(text)
        origem   = self._extract_origem(text)

        # ── 2. Listar operadores de um setor ──────────────────────────────────
        if self._OPERADOR.search(low) and (self._LISTA.search(low) or self._QUEM.search(low)):
            return InterpretationResult(
                intent="list_operadores_revisao", route="sql",
                metric="operadores_revisao",
                setor=setor or "revisao",
                confidence=0.90, reasoning="Listagem de operadores por setor.",
            )

        # ── 3. Ranking de produto com mais LD ─────────────────────────────────
        if self._LD.search(low) and self._PRODUTO.search(low) and (self._QUAL.search(low) or self._RANKING.search(low) or self._TOP.search(low)):
            return InterpretationResult(
                intent="ranking_produtos_ld", route="sql",
                metric="geracao_ld", entity_type="produto",
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                top_n=top_n or 5,
                setor=setor,
                origem=origem,
                confidence=0.88,
                reasoning="Ranking de produtos por geração de LD.",
            )

        # ── 4. Ranking / top N usuários com mais LD ───────────────────────────
        if self._LD.search(low) and (self._RANKING.search(low) or self._TOP.search(low) or self._QUEM.search(low)):
            return InterpretationResult(
                intent="ranking_usuarios_ld", route="sql",
                metric="geracao_ld", entity_type="operador",
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                top_n=top_n or 5,
                setor=setor,
                origem=origem,
                confidence=0.89,
                reasoning="Ranking de operadores por LD.",
            )

        # ── 5. LD por operador específico ─────────────────────────────────────
        if self._LD.search(low) and (self._GERACAO.search(low) or self._PRODUCAO.search(low) or operador):
            return InterpretationResult(
                intent="geracao_ld_por_operador", route="sql",
                metric="geracao_ld", entity_type="operador",
                entity_value=operador,
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                setor=setor,
                origem=origem,
                confidence=0.85 if operador else 0.65,
                reasoning="Geração de LD por operador.",
            )

        # ── 6. Ranking geral de produção (sem LD) ─────────────────────────────
        if self._RANKING.search(low) or self._TOP.search(low):
            return InterpretationResult(
                intent="ranking_producao_geral", route="sql",
                metric="producao_total", entity_type="operador",
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                top_n=top_n or 5,
                setor=setor,
                origem=origem,
                confidence=0.82,
                reasoning="Ranking geral de produção.",
            )

        # ── 7. Produção por produto específico ───────────────────────────────
        if produto and self._PRODUCAO.search(low):
            return InterpretationResult(
                intent="producao_por_produto", route="sql",
                metric="producao_total", entity_type="produto",
                entity_value=produto,
                produto_filtro=produto,
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                origem=origem,
                confidence=0.87,
                reasoning="Produção de produto específico.",
            )

        # ── 8. Produção por turno ─────────────────────────────────────────────
        if self._TURNO.search(low):
            return InterpretationResult(
                intent="producao_por_turno", route="sql",
                metric="producao_total", entity_type="turno",
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                setor=setor,
                origem=origem,
                confidence=0.88,
                reasoning="Produção agrupada por turno.",
            )

        # ── 9. Total geral da fábrica ─────────────────────────────────────────
        if self._TOTAL.search(low) and not operador:
            return InterpretationResult(
                intent="total_fabrica", route="sql",
                metric="producao_total",
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                setor=setor,
                origem=origem,
                confidence=0.85,
                reasoning="Total geral de produção da fábrica.",
            )

        # ── 10. Produção por operador específico ──────────────────────────────
        if self._PRODUCAO.search(low) or operador:
            return InterpretationResult(
                intent="producao_por_operador", route="sql",
                metric="producao_total", entity_type="operador",
                entity_value=operador,
                data_inicio=data_inicio or "01/01/2025",
                data_fim=data_fim or "31/12/2026",
                period_text=period_text,
                confidence=0.80 if operador else 0.60,
                reasoning="Produção total por operador.",
            )

        # ── Fallback ──────────────────────────────────────────────────────────
        return InterpretationResult(
            intent="clarify", route="clarify",
            confidence=0.40,
            reasoning="Nenhuma intenção identificada com segurança.",
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_top_n(self, text: str) -> int | None:
        m = _RE_TOP_N.search(text)
        if m:
            return int(m.group(1))
        m2 = re.search(r"\b(\d+)\s+(?:usuário|operador|produto)", text, re.IGNORECASE)
        if m2:
            return int(m2.group(1))
        return None

    def _extract_operator(self, text: str) -> str | None:
        # Padrão nome.sobrenome explícito no texto
        m = _RE_OPERATOR.search(text)
        if m:
            candidate = m.group(1).lower()
            # Valida se está na lista de operadores conhecidos
            if candidate in todos_operadores():
                return candidate
            return candidate  # aceita mesmo desconhecido

        # Primeiro nome dos operadores cadastrados
        for operador in todos_operadores():
            primeiro_nome = operador.split(".")[0]
            if re.search(rf"\b{re.escape(primeiro_nome)}\b", text, re.IGNORECASE):
                return operador
        return None

    def _extract_setor(self, text: str) -> str | None:
        """Detecta menção a um setor no texto."""
        low = text.lower()
        for setor_alias in ["expedição", "expedicao", "expedicão", "revisão", "revisao"]:
            if setor_alias in low:
                return _normalizar_setor(setor_alias)
        return None

    def _extract_origem(self, text: str) -> str | None:
        """Detecta tipo de movimentação (SD1/SD2/SD3 ou por nome)."""
        low = text.lower()
        # Código direto
        for codigo in ORIGENS:
            if codigo.lower() in low:
                return codigo
        # Por nome
        if re.search(r"entrada", low):
            return "SD1"
        if re.search(r"sa[íi]da", low):
            return "SD2"
        if re.search(r"movimenta[cç][aã]o\s+interna|interna", low):
            return "SD3"
        return None

    def _extract_produto_code(self, text: str) -> str | None:
        m = _RE_PRODUTO.search(text)
        return m.group(1).upper() if m else None
