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

Períodos suportados:
  hoje, ontem, esta semana, semana passada, últimos N dias,
  mês passado, este mês, nesse mês, desse mês, ano passado, este ano,
  "janeiro de 2026", "março 2025", "em fevereiro", "em 2025"

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
_MESES_PATTERN = "|".join(sorted(MESES, key=len, reverse=True))

# ── Patterns de período compilados ────────────────────────────────────────────
_RE_MONTH_YEAR = re.compile(
    r"\b(" + _MESES_PATTERN + r")\b"
    r"(?:\s+de\s+|\s+)?"
    r"(20\d{2})?",
    re.IGNORECASE,
)
_RE_YEAR_ONLY       = re.compile(r"\b(20\d{2})\b")
_RE_DATA_ESPECIFICA = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(20\d{2})(?!\d)")          # DD/MM/YYYY
_RE_DATA_DIA_MES    = re.compile(r"(?:no?\s+)?dia\s+(\d{1,2})/(\d{1,2})(?!/\d)", re.IGNORECASE)  # dia DD/MM
_RE_DATA_DIA_MES_LIVRE = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!/\d)")  # DD/MM sem ano
_RE_DATA_DIA_MES_NOME = re.compile(
    r"\b(?:no\s+dia|dia|em)\s+(\d{1,2})\s+de\s+(" + _MESES_PATTERN + r")\b"
    r"(?:\s+(?:de\s+)?(20\d{2}))?",
    re.IGNORECASE,
)  # dia 1 de abril / em 1 de abril de 2026
_RE_DATA_DIA_MES_NOME_ENDPOINT = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + _MESES_PATTERN + r")\b"
    r"(?:\s+(?:de\s+)?(20\d{2}))?",
    re.IGNORECASE,
)  # usado em endpoints de intervalo: "1 de abril ate 3 de abril"
_RE_DATA_DIA_SO = re.compile(r"\b(?:no\s+dia|dia)\s+(\d{1,2})(?!\s*/|\s+de\s+)", re.IGNORECASE)
# "dia 20 do mes passado" / "dia 5 do mes anterior" — extrai dia num mês relativo
_RE_DATA_DIA_MES_RELATIVO = re.compile(
    r"\b(?:no\s+dia|dia)\s+(\d{1,2})\s+do\s+m[eê]s\s+(?:passado|anterior)",
    re.IGNORECASE,
)
_RE_TOP_N           = re.compile(r"\btop\s*(\d+)\b", re.IGNORECASE)
_RE_OPERATOR  = re.compile(r"\b([a-záéíóúâêîôûãõç]+\.[a-záéíóúâêîôûãõç]+)\b", re.IGNORECASE)
_RE_PRODUTO   = re.compile(r"\b(TD2[A-Z0-9]{2,})\b", re.IGNORECASE)

# Expressões temporais — ordem importa (mais específico primeiro)
_RE_ONTEM        = re.compile(r"\bontem\b", re.IGNORECASE)
_RE_HOJE         = re.compile(r"\bhoje\b|\bno\s+dia\s+de\s+hoje\b", re.IGNORECASE)
_RE_SEMANA_PASS  = re.compile(r"semana\s+passada|semana\s+anterior", re.IGNORECASE)
_RE_SEMANA_ATUAL = re.compile(
    r"esta\s+semana|essa\s+semana|nessa\s+semana|nesta\s+semana|"
    r"semana\s+atual|semana\s+corrente",
    re.IGNORECASE,
)
_RE_ULTIMOS_DIAS  = re.compile(r"[uú]ltimos?\s+(\d+)\s+dias?", re.IGNORECASE)
_RE_ULTIMOS_MESES = re.compile(r"[uú]ltimos?\s+(\d+)\s+meses?", re.IGNORECASE)
_RE_MES_PASS     = re.compile(r"m[eê]s\s+passado|m[eê]s\s+anterior", re.IGNORECASE)
_RE_MES_ATUAL    = re.compile(
    r"este\s+m[eê]s|m[eê]s\s+atual|nesse\s+m[eê]s|neste\s+m[eê]s|"
    r"desse\s+m[eê]s|deste\s+m[eê]s|esse\s+m[eê]s|m[eê]s\s+corrente|"
    r"no\s+m[eê]s\s+atual|"
    r"do\s+m[eê]s(?!\s+(?:passado|anterior))",  # "do mes" sem qualificador = mês atual
    re.IGNORECASE,
)
_RE_ANO_PASS     = re.compile(r"ano\s+passado|ano\s+anterior", re.IGNORECASE)
_RE_ANO_ATUAL    = re.compile(
    r"este\s+ano|ano\s+atual|esse\s+ano|neste\s+ano|nesse\s+ano|"
    r"ano\s+corrente",
    re.IGNORECASE,
)


# ── Funções de período ────────────────────────────────────────────────────────

def _mes_nome(mes: int) -> str:
    """Retorna o nome completo do mês em português capitalizado."""
    return list(MESES.keys())[list(MESES.values()).index(mes)].capitalize()


def _parse_endpoint(text: str, as_start: bool) -> str | None:
    """
    Converte um texto de endpoint em DD/MM/YYYY.

    as_start=True  → primeiro dia do período (ex: "agosto de 2025" → "01/08/2025")
    as_start=False → último dia do período   (ex: "agosto de 2025" → "31/08/2025")

    Reconhece: hoje, ontem, este mês, mês passado, este ano, ano passado,
               "agosto de 2025", "agosto 2025", "agosto", "2025".
    """
    today = date.today()
    s = text.strip().lower()

    if _RE_HOJE.search(s):
        return today.strftime("%d/%m/%Y")

    if _RE_ONTEM.search(s):
        return (today - timedelta(days=1)).strftime("%d/%m/%Y")

    if _RE_SEMANA_PASS.search(s):
        inicio = today - timedelta(days=today.weekday() + 7)
        fim    = inicio + timedelta(days=6)
        return inicio.strftime("%d/%m/%Y") if as_start else fim.strftime("%d/%m/%Y")

    if _RE_SEMANA_ATUAL.search(s):
        inicio = today - timedelta(days=today.weekday())
        fim    = inicio + timedelta(days=6)
        return inicio.strftime("%d/%m/%Y") if as_start else fim.strftime("%d/%m/%Y")

    if _RE_MES_ATUAL.search(s):
        if as_start:
            return today.replace(day=1).strftime("%d/%m/%Y")
        ultimo = calendar.monthrange(today.year, today.month)[1]
        return today.replace(day=ultimo).strftime("%d/%m/%Y")

    if _RE_MES_PASS.search(s):
        primeiro = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        if as_start:
            return primeiro.strftime("%d/%m/%Y")
        ultimo = calendar.monthrange(primeiro.year, primeiro.month)[1]
        return primeiro.replace(day=ultimo).strftime("%d/%m/%Y")

    if _RE_ANO_ATUAL.search(s):
        if as_start:
            return f"01/01/{today.year}"
        return f"31/12/{today.year}"

    if _RE_ANO_PASS.search(s):
        ano = today.year - 1
        if as_start:
            return f"01/01/{ano}"
        return f"31/12/{ano}"

    # "19/04/2026" / "dia 19/04/2026"
    m_data = _RE_DATA_ESPECIFICA.search(s)
    if m_data:
        try:
            d = date(int(m_data.group(3)), int(m_data.group(2)), int(m_data.group(1)))
            return d.strftime("%d/%m/%Y")
        except ValueError:
            pass

    # "dia 19/04" (sem ano → ano atual)
    m_dia = _RE_DATA_DIA_MES.search(s)
    if m_dia:
        try:
            d = date(today.year, int(m_dia.group(2)), int(m_dia.group(1)))
            return d.strftime("%d/%m/%Y")
        except ValueError:
            pass

    m_dia_livre = _RE_DATA_DIA_MES_LIVRE.search(s)
    if m_dia_livre:
        try:
            d = date(today.year, int(m_dia_livre.group(2)), int(m_dia_livre.group(1)))
            return d.strftime("%d/%m/%Y")
        except ValueError:
            pass

    m_dia_nome = _RE_DATA_DIA_MES_NOME.search(s) or _RE_DATA_DIA_MES_NOME_ENDPOINT.search(s)
    if m_dia_nome:
        try:
            dia = int(m_dia_nome.group(1))
            mes = MESES[m_dia_nome.group(2).lower()]
            ano = int(m_dia_nome.group(3)) if m_dia_nome.group(3) else today.year
            d = date(ano, mes, dia)
            return d.strftime("%d/%m/%Y")
        except (KeyError, ValueError):
            pass

    # "dia 20 do mes passado" — antes do DIA_SO genérico
    m_dia_mes_rel = _RE_DATA_DIA_MES_RELATIVO.search(s)
    if m_dia_mes_rel:
        primeiro = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        try:
            d = date(primeiro.year, primeiro.month, int(m_dia_mes_rel.group(1)))
            return d.strftime("%d/%m/%Y")
        except ValueError:
            pass

    m_dia_so = _RE_DATA_DIA_SO.search(s)
    if m_dia_so:
        try:
            d = date(today.year, today.month, int(m_dia_so.group(1)))
            return d.strftime("%d/%m/%Y")
        except ValueError:
            pass

    # "agosto de 2025" / "agosto 2025" / "agosto"
    m = _RE_MONTH_YEAR.search(s)
    if m:
        mes_str = m.group(1).lower()
        ano_str = m.group(2)
        mes = MESES.get(mes_str)
        if mes:
            ano = int(ano_str) if ano_str else today.year
            if as_start:
                return f"01/{mes:02d}/{ano}"
            ultimo = calendar.monthrange(ano, mes)[1]
            return f"{ultimo:02d}/{mes:02d}/{ano}"

    # "2025"
    m2 = _RE_YEAR_ONLY.search(s)
    if m2:
        ano = int(m2.group(1))
        if as_start:
            return f"01/01/{ano}"
        return f"31/12/{ano}"

    return None


def _try_parse_range(text: str) -> tuple[str | None, str | None, str | None] | None:
    """
    Tenta extrair um intervalo de datas (data_inicio, data_fim, label) de texto livre.

    Padrões reconhecidos (em ordem de prioridade):
      "de agosto de 2025 até hoje"
      "desde março de 2025 até abril de 2026"
      "de janeiro até este mês"
      "entre agosto de 2025 e hoje"
      "de agosto a dezembro de 2025"   ← "a" como separador (quando Y é mês/hoje/ano)

    Retorna None se nenhum padrão de intervalo for encontrado.
    """
    lowered = text.lower()

    # ── Padrão 1: "de/desde X até Y" — "até" é separador inequívoco ─────────
    for sep in (" até ", " ate "):
        if sep in lowered:
            partes = lowered.split(sep, 1)
            ini_txt = re.sub(r"^(?:de|desde)\s+", "", partes[0].strip())
            fim_txt = partes[1].strip()
            ini = _parse_endpoint(ini_txt, as_start=True)
            fim = _parse_endpoint(fim_txt, as_start=False)
            if ini and fim:
                return ini, fim, f"{ini_txt} até {fim_txt}"

    # ── Padrão 2: "entre X e Y" ───────────────────────────────────────────────
    m = re.search(r"\bentre\s+(.+?)\s+e\s+(.+)", lowered)
    if m:
        ini_txt = m.group(1).strip()
        fim_txt = m.group(2).strip()
        ini = _parse_endpoint(ini_txt, as_start=True)
        fim = _parse_endpoint(fim_txt, as_start=False)
        if ini and fim:
            return ini, fim, f"{ini_txt} a {fim_txt}"

    # ── Padrão 3: "de/desde X a Y" — "a" como separador ────────────────────
    # Só ativa quando Y começa com mês nomeado, "hoje", "ontem" ou ano (evita FP)
    m = re.search(
        rf"(?:de|desde)\s+(.+?)\s+a\s+({_MESES_PATTERN}|hoje|ontem|este\s+m[eê]s|este\s+ano|\d{{4}})((?:\s+.+)?)",
        lowered,
    )
    if m:
        ini_txt = m.group(1).strip()
        fim_txt = (m.group(2) + m.group(3)).strip()
        ini = _parse_endpoint(ini_txt, as_start=True)
        fim = _parse_endpoint(fim_txt, as_start=False)
        if ini and fim:
            return ini, fim, f"{ini_txt} a {fim_txt}"

    return None


_PATTERNS_TWO_PERIODS = [
    # "compare X com Y" / "compare X e Y" / "compare X versus Y"
    re.compile(r"compar[ae]\w*\s+(.+?)\s+(?:com|e|versus|vs\.?)\s+(.+)", re.IGNORECASE),
    # "diferença de X para Y" / "diferença entre X e Y"
    re.compile(r"diferen[cç]a\s+(?:de|entre)\s+(.+?)\s+(?:e|para|pra|a)\s+(.+)", re.IGNORECASE),
    # "X versus Y" / "X vs Y"
    re.compile(r"(.+?)\s+(?:versus|vs\.?)\s+(.+)", re.IGNORECASE),
    # "cresceu/caiu/evoluiu de X para Y"
    re.compile(
        r"(?:cresceu|caiu|aumentou|diminuiu|evoluiu|variou)\w*\s+de\s+(.+?)\s+(?:para|pra|a)\s+(.+)",
        re.IGNORECASE,
    ),
    # "como foi/ficou de X para Y"
    re.compile(
        r"como\s+(?:foi|ficou|andou)\s+de\s+(.+?)\s+(?:para|pra|a)\s+(.+)",
        re.IGNORECASE,
    ),
]


def _try_parse_two_periods(
    text: str,
) -> tuple[str, str, str, str, str, str] | None:
    """
    Tenta extrair dois períodos distintos de texto de comparação.

    Reconhece padrões como:
      "compare janeiro com fevereiro"
      "diferença entre semana passada e esta semana"
      "janeiro versus fevereiro"
      "cresceu de março para abril"

    Retorna (ini1, fim1, lbl1, ini2, fim2, lbl2) ou None se não reconhecer.
    Usa _parse_endpoint para converter cada lado em DD/MM/YYYY.
    """
    lowered = text.lower()
    for pattern in _PATTERNS_TWO_PERIODS:
        m = pattern.search(lowered)
        if not m:
            continue
        txt1 = m.group(1).strip()
        txt2 = m.group(2).strip()
        ini1 = _parse_endpoint(txt1, as_start=True)
        fim1 = _parse_endpoint(txt1, as_start=False)
        ini2 = _parse_endpoint(txt2, as_start=True)
        fim2 = _parse_endpoint(txt2, as_start=False)
        if ini1 and fim1 and ini2 and fim2:
            _, _, lbl1 = _periodo_from_text(txt1)
            _, _, lbl2 = _periodo_from_text(txt2)
            return ini1, fim1, lbl1 or txt1.capitalize(), ini2, fim2, lbl2 or txt2.capitalize()
    return None


def _default_periodo() -> tuple[str, str, str]:
    """
    Retorna o mês atual como período padrão quando nenhum for especificado.
    Substitui os hardcodes '01/01/2025' e '31/12/2026'.
    """
    today = date.today()
    primeiro = today.replace(day=1)
    ultimo_dia = calendar.monthrange(today.year, today.month)[1]
    ultimo = today.replace(day=ultimo_dia)
    return (
        primeiro.strftime("%d/%m/%Y"),
        ultimo.strftime("%d/%m/%Y"),
        f"{_mes_nome(today.month)} de {today.year}",
    )


def _periodo_from_text(text: str) -> tuple[str | None, str | None, str | None]:
    """
    Extrai (data_inicio, data_fim, period_label) a partir de texto livre.
    Retorna strings no formato DD/MM/YYYY, ou (None, None, None) se não encontrar.

    Suporta períodos simples:
      hoje, ontem, esta semana, semana passada, últimos N dias,
      mês passado, este/esse/nesse/desse mês, ano passado, este ano,
      "janeiro de 2026", "março 2025", "em fevereiro", "em 2025".

    Suporta intervalos entre períodos:
      "de agosto de 2025 até hoje"
      "desde março de 2025 até abril de 2026"
      "entre agosto e dezembro de 2025"
      "de agosto a dezembro de 2025"
    """
    today   = date.today()
    lowered = text.lower()

    # ── Intervalos entre períodos (prioridade máxima) ─────────────────────────
    range_result = _try_parse_range(text)
    if range_result:
        ini_range, fim_range, _lbl_range = range_result
        return ini_range, fim_range, f"{ini_range} até {fim_range}"

    # "ontem"
    if _RE_ONTEM.search(lowered):
        ontem = today - timedelta(days=1)
        d = ontem.strftime("%d/%m/%Y")
        return d, d, f"ontem ({d})"

    # "hoje"
    if _RE_HOJE.search(lowered):
        d = today.strftime("%d/%m/%Y")
        return d, d, f"hoje ({d})"

    # "semana passada"
    if _RE_SEMANA_PASS.search(lowered):
        inicio = today - timedelta(days=today.weekday() + 7)
        fim    = inicio + timedelta(days=6)
        return inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"), "semana passada"

    # "esta/essa/nessa semana"
    if _RE_SEMANA_ATUAL.search(lowered):
        inicio = today - timedelta(days=today.weekday())
        fim    = inicio + timedelta(days=6)
        return inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"), "esta semana"

    # "últimos N dias"
    m_dias = _RE_ULTIMOS_DIAS.search(lowered)
    if m_dias:
        n     = int(m_dias.group(1))
        inicio = today - timedelta(days=n - 1)
        return (
            inicio.strftime("%d/%m/%Y"),
            today.strftime("%d/%m/%Y"),
            f"últimos {n} dias",
        )

    # "19/04/2026" / "no dia 19/04/2026" / "dia 19/04/2026"
    m_data = _RE_DATA_ESPECIFICA.search(text)
    if m_data:
        try:
            d = date(int(m_data.group(3)), int(m_data.group(2)), int(m_data.group(1)))
            ds = d.strftime("%d/%m/%Y")
            return ds, ds, f"dia {ds}"
        except ValueError:
            pass

    # "dia 19/04" / "no dia 19/04" (sem ano → ano atual)
    m_dia_mes = _RE_DATA_DIA_MES.search(text)
    if m_dia_mes:
        try:
            d = date(today.year, int(m_dia_mes.group(2)), int(m_dia_mes.group(1)))
            ds = d.strftime("%d/%m/%Y")
            return ds, ds, f"dia {ds}"
        except ValueError:
            pass

    m_dia_mes_livre = _RE_DATA_DIA_MES_LIVRE.search(text)
    if m_dia_mes_livre:
        try:
            d = date(today.year, int(m_dia_mes_livre.group(2)), int(m_dia_mes_livre.group(1)))
            ds = d.strftime("%d/%m/%Y")
            return ds, ds, f"dia {ds}"
        except ValueError:
            pass

    # "dia 1 de abril" / "em 1 de abril de 2026"
    m_dia_nome = _RE_DATA_DIA_MES_NOME.search(text)
    if m_dia_nome:
        try:
            dia = int(m_dia_nome.group(1))
            mes = MESES[m_dia_nome.group(2).lower()]
            ano = int(m_dia_nome.group(3)) if m_dia_nome.group(3) else today.year
            d = date(ano, mes, dia)
            ds = d.strftime("%d/%m/%Y")
            return ds, ds, f"dia {ds}"
        except (KeyError, ValueError):
            pass

    # "dia 20 do mes passado" / "dia 5 do mes anterior" — antes do DIA_SO genérico
    m_dia_mes_rel = _RE_DATA_DIA_MES_RELATIVO.search(text)
    if m_dia_mes_rel:
        primeiro = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        try:
            d = date(primeiro.year, primeiro.month, int(m_dia_mes_rel.group(1)))
            ds = d.strftime("%d/%m/%Y")
            return ds, ds, f"dia {ds}"
        except ValueError:
            pass

    # "dia 1" / "no dia 1" (sem mes explicito -> mes atual)
    m_dia_so = _RE_DATA_DIA_SO.search(text)
    if m_dia_so:
        try:
            d = date(today.year, today.month, int(m_dia_so.group(1)))
            ds = d.strftime("%d/%m/%Y")
            return ds, ds, f"dia {ds}"
        except ValueError:
            pass

    # "últimos N meses"
    m_meses = _RE_ULTIMOS_MESES.search(lowered)
    if m_meses:
        n = int(m_meses.group(1))
        mes = today.month - n
        ano = today.year
        while mes <= 0:
            mes += 12
            ano -= 1
        inicio_d = date(ano, mes, 1)
        return (
            inicio_d.strftime("%d/%m/%Y"),
            today.strftime("%d/%m/%Y"),
            f"últimos {n} meses",
        )

    # "mês passado / anterior"
    if _RE_MES_PASS.search(lowered):
        primeiro  = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
        ultimo_dia = calendar.monthrange(primeiro.year, primeiro.month)[1]
        ultimo    = primeiro.replace(day=ultimo_dia)
        return (
            primeiro.strftime("%d/%m/%Y"),
            ultimo.strftime("%d/%m/%Y"),
            f"{_mes_nome(primeiro.month)} de {primeiro.year}",
        )

    # "este mês / mês atual / nesse mês / desse mês / esse mês / ..."
    if _RE_MES_ATUAL.search(lowered):
        primeiro  = today.replace(day=1)
        ultimo_dia = calendar.monthrange(today.year, today.month)[1]
        ultimo    = today.replace(day=ultimo_dia)
        return (
            primeiro.strftime("%d/%m/%Y"),
            ultimo.strftime("%d/%m/%Y"),
            f"{_mes_nome(today.month)} de {today.year}",
        )

    # "ano passado / anterior"
    if _RE_ANO_PASS.search(lowered):
        ano = today.year - 1
        return f"01/01/{ano}", f"31/12/{ano}", str(ano)

    # "este ano / ano atual / esse ano"
    if _RE_ANO_ATUAL.search(lowered):
        ano = today.year
        return f"01/01/{ano}", f"31/12/{ano}", str(ano)

    # "janeiro de 2026" / "janeiro 2026" / "em janeiro"
    m = _RE_MONTH_YEAR.search(lowered)
    if m:
        mes_str  = m.group(1).lower()
        ano_str  = m.group(2)
        mes      = MESES[mes_str]
        ano      = int(ano_str) if ano_str else today.year
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


# ── Interpretador ─────────────────────────────────────────────────────────────

class RuleBasedInterpreter:
    """
    Interpretador baseado em regras para o setor de Produção.
    Cobre: LD, produção total, rankings, produtos, turnos, comparações.
    Suporta referências temporais ampliadas e primeira pessoa ("meu LD", "minha produção").
    """

    # ── Agrupamentos de palavras-chave — cobertura ampliada ───────────────────

    # Qualidade do material — LD, Inteiro, Fora de Padrão e qualidade geral
    # Qualquer menção a qualidade → roteia para V_KARDEX (breakdown Inteiro/LD/FP)
    _LD = re.compile(
        r"\bld\b|\blaudo\s+de?\s+defeito\b|\bmaterial\s+(?:com\s+)?defeito\b|"
        r"\bdefeituoso\b|\bdefeito\b|"
        r"\binteiro\b|\bsem\s+defeito\b|"
        r"\bfora\s+de\s+padr[aã]o\b|\bfora\s+do\s+padr[aã]o\b|\bfp\b|"
        r"por\s+qualidade|qualidade\s+da\s+produ[cç][aã]o|"
        r"qualidade\s+do\s+material|diferenciar\s+(?:ld|inteiro|qualidade)|"
        r"separar\s+(?:por\s+)?qualidade|dividir\s+(?:por\s+)?qualidade",
        re.IGNORECASE,
    )

    _QUALIDADE_RESUMO = re.compile(
        r"\binteiro\b|\bsem\s+defeito\b|"
        r"\bfora\s+de\s+padr[aã]o\b|\bfora\s+do\s+padr[aã]o\b|\bfp\b|"
        r"por\s+qualidade|qualidade\s+da\s+produ[cç][aã]o|"
        r"qualidade\s+do\s+material|diferenciar\s+(?:ld|inteiro|qualidade)|"
        r"separar\s+(?:por\s+)?qualidade|dividir\s+(?:por\s+)?qualidade|"
        r"resumo\s+de\s+qualidade|quebra\s+por\s+qualidade",
        re.IGNORECASE,
    )

    # Perda de material = LD + BAG (defeitos que saem do processo)
    _PERDA = re.compile(
        # Termos diretos de perda
        r"perda[s]?\s+(?:de\s+)?(?:material|produ[cç][aã]o|bobina[s]?)|"
        r"\bperdas?\b(?!\s+de\s+tempo)|"              # "perda" genérica, exceto "perda de tempo"
        r"material\s+(?:(?:foi|est[aá]|ficou)\s+)?(?:perdido[s]?|descartado[s]?|rejeitado[s]?|refugado[s]?)|"
        r"quanto\s+(?:foi\s+|de\s+)?(?:material\s+)?(?:perdido|descartado|rejeitado)|quanto\s+perdemos?|"
        r"total\s+(?:de\s+)?perda[s]?|[ií]ndice\s+(?:de\s+)?perda[s]?|taxa\s+(?:de\s+)?perda[s]?|"
        # Descarte / rejeito / refugo
        r"descarte[s]?\s+(?:de\s+)?material|rejeito[s]?\s+(?:de\s+)?material|"
        r"\brejeito[s]?\b|\brefugo\b|"
        r"material\s+(?:descartado|rejeitado|refugado)|"
        # Desperdício
        r"desperd[ií]cio[s]?|material\s+desperdi[cç]ado|quanto\s+desperdi[cç]amos?|"
        # LD + BAG explícito
        r"ld\s+(?:e|mais|com)\s+bag|bag\s+(?:e|mais|com)\s+ld|soma\s+(?:de\s+)?(?:ld|bag)|"
        # Perda vs produção / em relação
        r"perda\s+(?:versus?\.?|em\s+rela[cç][aã]o|comparad[ao])|"
        r"quanto\s+(?:da\s+)?produ[cç][aã]o\s+(?:foi\s+)?perda|"
        r"perda[s]?\s+(?:em\s+rela[cç][aã]o\s+[aà]|da|da\s+)?produ[cç][aã]o",
        re.IGNORECASE,
    )

    # LD solicitado em metros (unidade MT) — filtra exibição para MT
    _METROS_UNIDADE = re.compile(
        r"\bem\s+metros?\b|\bem\s+mt\b|metros?\s+de\s+ld|quantos?\s+metros?\s+de\s+ld|"
        r"medido\s+em\s+metros?|ld\s+em\s+metros?",
        re.IGNORECASE,
    )

    # Ações de geração/identificação (revisão)
    _GERACAO = re.compile(
        r"gera[cç][aã]o|gerou|gerada|geradas|gerou|"
        r"identificou|identificar|identificado|identificados|identifiquei|"
        r"encontrou|encontrar|encontrado|encontrou|encontrei|"
        r"detectou|detectar|detectado|detectei|"
        r"levantou|levantado|"
        r"inspecionou|inspecionado|inspecionei|"
        r"revisou|revisado|revisei|"
        r"apontou|apontado|apontei",
        re.IGNORECASE,
    )

    # Produção (extrusora, fabricação)
    _PRODUCAO = re.compile(
        r"produ[cç][aã]o|produziu|produzido|produzidos|produzir|produzi|"
        r"extrusora|bobina[s]?|fabricou|fabricado|fabricei|fabricar|"
        r"saiu\s+da\s+m[aá]quina|saiu\s+da\s+extrusora|"
        r"quanto\s+(?:foi\s+)?produzido|quanto\s+(?:o\s+)?fez|quanto\s+(?:a\s+)?f[aá]brica|"
        r"quanto\s+saiu|o\s+que\s+saiu|o\s+que\s+foi\s+(?:feito|produzido)|"
        r"o\s+que\s+a\s+(?:f[aá]brica|m[aá]quina|extrusora)\s+fez|"
        r"m[aá]quina\s+(?:produziu|fez)|linha\s+(?:produziu|fez)",
        re.IGNORECASE,
    )

    # Rankings e comparações de desempenho
    _RANKING = re.compile(
        r"ranking|classifica[cç][aã]o|quem\s+mais|mais\s+produziu|maior\s+produt|"
        r"l[ií]der|lideran[cç]a|melhor\s+(?:do|da|no|na|de)|"
        r"destaque|destacou|se\s+destacou|"
        r"primeiro\s+lugar|em\s+primeiro|"
        r"maior\s+volume|mais\s+identificou|mais\s+gerou|mais\s+encontrou|"
        r"quem\s+tem\s+mais|maior\s+produtor|mais\s+revisou|"
        # Variações de "apontou/gerou/identificou mais" — cobrem "qual usuário apontou mais LD"
        r"mais\s+apontou|apontou\s+mais|quem\s+apontou|"
        r"gerou\s+mais|identificou\s+mais|encontrou\s+mais|revisou\s+mais|produziu\s+mais|"
        r"maior\s+gerador|maior\s+apontamento|maior\s+identificador|"
        # "qual usuário/operador/pessoa que mais" — sem exigir "quem"
        r"usu[aá]rio\s+(?:que\s+)?(?:mais|com\s+mais)|"
        r"operador\s+(?:que\s+)?(?:mais|com\s+mais)|"
        r"pessoa\s+(?:que\s+)?(?:mais|com\s+mais)|"
        # "por operador" — "produção por operador", "KGH por operador"
        r"por\s+operador|individual(?:mente)?",
        re.IGNORECASE,
    )

    _TOP = re.compile(r"\btop\b", re.IGNORECASE)

    # Produto específico
    _PRODUTO = re.compile(
        r"\bprodutos?\b|\bmaterial(?:is)?\b|\breferencia\b|\breferência\b|"
        r"\bcódigo\b|\bcodigo\b|"
        r"qual\s+produtos?|qual\s+material|que\s+produtos?|que\s+material|"
        r"produtos?\s+(?:com\s+)?mais|material(?:is)?\s+(?:com\s+)?mais",
        re.IGNORECASE,
    )

    # Turno de trabalho
    _TURNO = re.compile(
        r"\bturno\b|\bturno\s*\d\b|\bturno\s*[ABC]\b|"
        r"por\s+turno|cada\s+turno|turnos?",
        re.IGNORECASE,
    )

    _DIA_A_DIA = re.compile(
        r"dia\s+a\s+dia|cada\s+dia|por\s+dia|diariamente|di[aá]rio|"
        r"m[eê]s\s+a\s+m[eê]s",
        re.IGNORECASE,
    )

    # Metros por minuto
    _METROS_MIN = re.compile(
        r"metro[s]?\s+por\s+minuto|m[/\s]min|metros?\s*/?\s*min|"
        r"velocidade\s+(?:da\s+)?(?:m[aá]quina|extrusora)|"
        r"m[/.]min\b",
        re.IGNORECASE,
    )

    # KGH — quilo por hora
    _KGH = re.compile(
        r"\bkgh\b|\bkg[/\s]h\b|kg\s+por\s+hora|quilo[s]?\s+por\s+hora|"
        r"produtividade\s+(?:em\s+)?kg",
        re.IGNORECASE,
    )

    # Extrusora / recurso específico
    _EXTRUSORA = re.compile(
        r"extrusora\s*([12])|mac\s*([12])|m[aá]quina\s*([12])|"
        r"max\s*([12])|"  # typo comum de MAC
        r"\b0003\b|\b0007\b",
        re.IGNORECASE,
    )

    # Referência genérica às máquinas de extrusão, mesmo sem número explícito
    # Inclui typos: "extrusara" (a↔o trocados), "extrusoras"
    _EXTRUSORA_REFERENCIA = re.compile(
        r"\bextrus[oa]r[ao]s?\b|\bmacs?\b|\bm[aá]quinas?\b",
        re.IGNORECASE,
    )

    # Comparativo entre extrusoras
    _COMPARATIVO = re.compile(
        r"compar[ae]|versus|vs\.?|\bx\b|contra|diferen[cç]a\s+entre|"
        r"qual\s+(?:extrusora|mac|m[aá]quina)\s+(?:mais|produziu|melhor)|"
        r"(?:extrusora|mac)\s*1\s+e\s+(?:extrusora|mac)?\s*2|"
        r"as\s+duas\s+(?:extrusoras?|m[aá]quinas?|macs?)|"
        r"lado\s+a\s+lado|por\s+(?:extrusora|m[aá]quina|mac)|"
        r"cada\s+(?:extrusora|m[aá]quina|mac)|"
        r"valor\s+(?:de|da)\s+cada\s+(?:extrusora|m[aá]quina|mac)|"
        r"valor\s+total\s+de\s+cada\s+(?:extrusora|m[aá]quina|mac)|"
        r"produ[cç][aã]o\s+exata\s+por\s+(?:extrusora|m[aá]quina|mac)|"
        r"produ[cç][aã]o\s+das\s+(?:extrusoras|m[aá]quinas|macs)",
        re.IGNORECASE,
    )

    # Ranking de revisão — apontamentos de bobinas revisadas (STG_APONT_REV_GERAL)
    # Distinguido do KARDEX/LD por combinar volume de revisão + contexto de ranking/produtividade.
    _RANKING_REVISAO = re.compile(
        r"quem\s+mais\s+revisou|ranking\s+(?:de\s+)?revis[aã]o|"
        r"produtividade\s+(?:da\s+)?revis[aã]o|"
        r"total\s+revisado|quanto\s+(?:foi\s+)?revisado|"
        r"produ[cç][aã]o\s+da\s+revis[aã]o|volume\s+(?:de\s+)?revis[aã]o|"
        r"kg\s+revisados?|kg\s+(?:da\s+)?revis[aã]o|"
        r"metros?\s+revisados?|mais\s+metros?\s+(?:na\s+)?revis[aã]o|"
        r"metros?\s+(?:na\s+|de\s+|da\s+)?revis[aã]o|revis[aã]o\s+(?:em\s+)?metros?|"
        r"mais\s+revisou|mais\s+revis[aã]o|quem\s+mais\s+revis",
        re.IGNORECASE,
    )

    _REVISAO = re.compile(r"revis[aã]o", re.IGNORECASE)

    # Horas trabalhadas
    _HORAS = re.compile(
        r"horas?\s+trabalhadas?|total\s+de\s+horas?|quantas?\s+horas?|"
        r"horas?\s+(?:de\s+)?(?:produ[cç][aã]o|trabalho|m[aá]quina|extrusora)|"
        r"tempo\s+(?:de\s+)?(?:produ[cç][aã]o|trabalho|operação)",
        re.IGNORECASE,
    )

    # Totais gerais da fábrica
    _TOTAL = re.compile(
        r"\btotal\b|\bf[aá]brica\b|\bfabrica\b|\bgeral\b|"
        r"resumo|vis[aã]o\s+geral|resultado\s+geral|geral\s+da\s+f[aá]brica|"
        r"total\s+(?:geral|da\s+f[aá]brica|de\s+produ[cç][aã]o)|"
        r"quanto\s+foi\s+(?:gerado|produzido)\s+no\s+total|"
        r"soma\s+(?:desses?|destes?|dos)\s+valores?|"
        r"somat[oó]rio\s+(?:desses?|destes?|dos)\s+valores?",
        re.IGNORECASE,
    )

    # Listagem de operadores
    _OPERADOR = re.compile(
        r"operador(?:es)?|revis[aã]o|revisor(?:es)?|"
        r"equipe\s+de|membros?\s+d[ao]",
        re.IGNORECASE,
    )

    _QUEM  = re.compile(r"\bquem\b", re.IGNORECASE)
    _QUAL  = re.compile(r"\bqual\b|\bquais\b", re.IGNORECASE)

    # Listagem
    _LISTA = re.compile(
        r"list[ae]|mostre|exib[ae]|quais|s[aã]o\s+os|"
        r"da\s+revis[aã]o|da\s+expedi[cç][aã]o|da\s+produ[cç][aã]o|"
        r"do\s+setor|do\s+departamento|nomes?\s+dos?",
        re.IGNORECASE,
    )

    # Expedição
    _EXPEDICAO = re.compile(
        r"expedi[cç][aã]o|expedido|expedida|expedidas|expedi|"
        r"liberado|liberados|liberadas|enviado|enviados|saiu\s+para\s+o\s+cliente|"
        r"bobinas?\s+liberadas?|saída\s+para\s+cliente",
        re.IGNORECASE,
    )

    # Primeira pessoa — o próprio usuário ("meu LD", "minha produção", "quanto eu")
    _PROPRIO = re.compile(
        r"\bminha?\s+produ[cç][aã]o\b|\bmeu\s+ld\b|\bmeu\s+resultado\b|"
        r"\bmeu\s+total\b|\bminha\s+revis[aã]o\b|\bmeu\s+desempenho\b|"
        r"\beu\s+(?:fiz|produzi|identifiquei|revisei|encontrei|detectei|gerei|apontei)\b|"
        r"\bquanto\s+eu\b|\bo\s+que\s+eu\b|\bno\s+meu\s+caso\b",
        re.IGNORECASE,
    )

    # Saudações curtas
    _SMALLTALK = re.compile(
        r"^(oi|ol[aá]|bom\s+dia|boa\s+tarde|boa\s+noite|"
        r"tudo\s+bem|tudo\s+bom|tudo\s+certo|e\s+a[ií]|"
        r"como\s+vai|como\s+voc[eê]\s+est[aá]|"
        r"obrigad[ao]|valeu|show|bl[zZ]|beleza|boa\b|"
        r"oi\s+tudo|e\s+a[ií]\s+gente|e\s+a[ií]\s+pessoal|"
        r"bom\s+dia\s+ayla|boa\s+tarde\s+ayla|boa\s+noite\s+ayla|"
        r"ol[aá]\s+ayla|oi\s+ayla|"
        r"preciso\s+de\s+ajuda|pode\s+me\s+ajudar|"
        r"ol[aá]\s+boa|e\s+a[ií]\s+boa|"
        r"at[eé]\s+mais|tchau|flw|falou|at[eé]\s+logo|"
        r"um\s+abra[cç]o|abraços|boa\s+sorte|"
        r"bom\s+trabalho|bom\s+fds|bom\s+fim\s+de\s+semana)\b",
        re.IGNORECASE,
    )

    # Conversa natural — perguntas e comentários que devem ir ao LLM
    _SMALLTALK_LONGA = re.compile(
        r"(como\s+voc[eê]\s+est[aá]|como\s+vai\s+voc[eê]|"
        r"quem\s+[eé]\s+voc[eê]|como\s+voc[eê]\s+se\s+chama|qual\s+(?:[eé]\s+)?seu\s+nome|"
        r"quem\s+sou\s+eu|qual\s+(?:[eé]\s+)?meu\s+(?:nome|setor|cargo)|"
        r"com\s+quem\s+estou\s+(?:falando|conversando)|"
        r"o\s+que\s+[eé]\s+ld|me\s+conta\s+sobre|"
        r"me\s+explica|conta\s+pra\s+mim|"
        r"quero\s+entender|n[aã]o\s+entendi|"
        r"boa\s+noite\s+vin|oi\s+vin|ol[aá]\s+vin|"
        r"o\s+que\s+[eé]\s+revis[aã]o|como\s+funciona|"
        r"me\s+d[aá]\s+uma\s+dica|me\s+ajuda\s+a\s+entender|"
        # conceitos e dúvidas sobre a fábrica
        r"o\s+que\s+[eé]\s+expedi[cç][aã]o|o\s+que\s+[eé]\s+turno|"
        r"o\s+que\s+[eé]\s+inteiro|o\s+que\s+[eé]\s+bobina|"
        r"como\s+[eé]\s+calculado|como\s+funciona\s+o|"
        r"qual\s+a\s+diferen[cç]a\s+entre|diferença\s+entre|"
        r"o\s+que\s+significa|o\s+que\s+quer\s+dizer|"
        r"pode\s+explicar|me\s+explique|me\s+fale\s+sobre|"
        r"tenho\s+uma\s+d[uú]vida|tenho\s+d[uú]vida|"
        r"n[aã]o\s+sei\s+o\s+que|n[aã]o\s+conhe[cç]o|"
        # feedback e comentários
        r"muito\s+bom|que\s+legal|que\s+[oó]timo|perfeito|"
        r"entendi|ficou\s+claro|[oó]timo\s+obrigad|"
        r"que\s+interessante|que\s+bacana|n[aã]o\s+sabia|"
        # pedidos de ajuda genéricos
        r"pode\s+me\s+dizer|pode\s+me\s+mostrar|pode\s+me\s+explicar|"
        r"me\s+d[aá]\s+uma\s+ideia|me\s+orienta|me\s+indica|"
        r"como\s+eu\s+fa[cç]o\s+para|o\s+que\s+eu\s+devo\s+perguntar|"
        r"como\s+eu\s+consulto|como\s+posso\s+ver|como\s+vejo)",
        re.IGNORECASE,
    )

    # Produção agrupada por produto (todos os produtos, sem filtro qualidade)
    _AGRUP_PRODUTO = re.compile(
        r"por\s+produto|total\s+por\s+produto|agrupado\s+(?:por\s+)?produto|"
        r"separad[ao]\s+(?:por\s+)?produto|desempenho\s+por\s+produto|"
        r"cada\s+produto|produto\s+(?:a\s+)?produto|"
        r"total\s+(?:de\s+)?cada\s+produto|quanto\s+(?:de\s+)?cada\s+produto",
        re.IGNORECASE,
    )

    # Produção por família (3 primeiros chars do código do produto)
    _FAMILIA_PRODUTO = re.compile(
        r"fam[ií]lia\s+(?:de\s+)?produto|por\s+fam[ií]lia|total\s+por\s+fam[ií]lia|"
        r"agrupado\s+(?:por\s+)?fam[ií]lia|cada\s+fam[ií]lia|"
        r"fam[ií]lia\s+de\s+produ[cç][aã]o",
        re.IGNORECASE,
    )

    # Comparações entre períodos
    _COMPARA = re.compile(
        r"compar[ae]|diferen[cç]a|versus|vs\.?|contra|"
        r"cresceu|caiu|aumentou|diminuiu|evolu[cç][aã]o|varia[cç][aã]o",
        re.IGNORECASE,
    )

    # Perguntas de definição/conceito — nunca vão ao banco independente do termo
    _DEFINICAO = re.compile(
        r"o\s+que\s+[eé]\s+|o\s+que\s+significa\s+|qual\s+(?:o\s+)?significado\s+(?:de\s+|do\s+)?|"
        r"me\s+explica\s+o\s+que\s+[eé]\s+|como\s+funciona\s+(?:o\s+|a\s+)?|"
        r"o\s+que\s+quer\s+dizer\s+|o\s+que\s+significa\s+|para\s+que\s+serve\s+|"
        r"qual\s+a\s+diferen[cç]a\s+entre\s+",
        re.IGNORECASE,
    )

    # Capacidades da IA — perguntas diretas sobre o que o agente sabe/faz
    _CAPACIDADES = re.compile(
        r"tipos?\s+de\s+informa[cç][aã]o|"
        r"o\s+que\s+voc[eê]\s+(?:consegue|pode|sabe|responde|faz)\b|"
        r"o\s+que\s+conseg[uo]\s+perguntar|"
        r"quais?\s+informa[cç][oõ]es\s+(?:voc[eê]\s+)?(?:tem|tem\s+acesso|pode|conseg)|"
        r"quais?\s+consultas\s+(?:posso|voc[eê]\s+faz)|"
        r"o\s+que\s+posso\s+perguntar\s+(?:pra|para)\s+voc[eê]|"
        r"capacidades?\s+(?:da|de)\s+(?:voc[eê]|ayla)|"
        r"funcionalidades?\s+(?:da|de)\s+(?:voc[eê]|ayla)|"
        r"como\s+(?:posso\s+usar|usar)\s+(?:voc[eê]|ayla)|"
        r"o\s+que\s+a\s+ayla\s+(?:faz|sabe|pode)|"
        r"me\s+mostra\s+(?:o\s+que\s+voc[eê]\s+(?:faz|sabe|pode))",
        re.IGNORECASE,
    )

    # Períodos disponíveis no banco
    _PERIODOS = re.compile(
        r"quais?\s+m[eê]ses?|quais?\s+anos?|per[ií]odos?\s+dispon[ií]veis?|"
        r"quais?\s+per[ií]odos?|que\s+per[ií]odos?|"
        r"desde\s+quando|at[eé]\s+quando|qual\s+(?:o\s+)?per[ií]odo|"
        r"quais?\s+dados?\s+(?:tem|tenho|temos|dispon[ií]veis?)|"
        r"de\s+quando\s+[aà]\s+quando|quais\s+datas|"
        r"hist[oó]rico\s+dispon[ií]vel|at[eé]\s+que\s+data",
        re.IGNORECASE,
    )

    # ── Ponto de entrada ──────────────────────────────────────────────────────

    def interpret(self, message: str) -> InterpretationResult:  # noqa: C901
        text = message.strip()
        low  = text.lower()

        # ── 1. Capacidades / o que a IA sabe fazer ───────────────────────────
        if self._CAPACIDADES.search(low) and not self._LD.search(low) and not self._PRODUCAO.search(low):
            return InterpretationResult(
                intent="tipos_informacao", route="smalltalk",
                confidence=0.95, reasoning="Pergunta sobre capacidades da IA.",
            )

        # ── 2. Períodos disponíveis no banco ──────────────────────────────────
        if self._PERIODOS.search(low):
            metric = None
            if self._LD.search(low) or "qualidade" in low:
                metric = "qualidade"
            elif self._REVISAO.search(low):
                metric = "revisao"
            elif self._PRODUCAO.search(low) or self._EXTRUSORA.search(low) or self._EXTRUSORA_REFERENCIA.search(low):
                metric = "producao"
            return InterpretationResult(
                intent="periodos_disponiveis", route="sql",
                metric=metric,
                confidence=0.93, reasoning="Pergunta sobre cobertura temporal dos dados.",
            )

        # ── 3. Saudação curta ─────────────────────────────────────────────────
        if self._SMALLTALK.search(low) and len(text.split()) <= 8:
            return InterpretationResult(
                intent="smalltalk", route="smalltalk",
                confidence=0.98, reasoning="Saudação identificada.",
            )

        # ── 3.5. Perguntas de definição/conceito — sempre smalltalk ──────────
        # Tem prioridade sobre qualquer regra SQL, mesmo que mencione LD/produção.
        # Ex: "O que é LD?", "O que significa FP?", "Qual a diferença entre Inteiro e LD?"
        if self._DEFINICAO.search(low):
            return InterpretationResult(
                intent="smalltalk", route="smalltalk",
                confidence=0.95, reasoning="Pergunta de definição/conceito — responde via glossário.",
            )

        # ── 4. Conversa natural longa ─────────────────────────────────────────
        # Guard: se a mensagem contém LD ou produção E tem período explícito,
        # deixa cair para as regras SQL — ex: "me fale sobre o LD de janeiro"
        _tem_dado = self._LD.search(low) or self._PRODUCAO.search(low) or self._EXPEDICAO.search(low)
        if self._SMALLTALK_LONGA.search(low) and not _tem_dado:
            return InterpretationResult(
                intent="smalltalk", route="smalltalk",
                confidence=0.90, reasoning="Conversa natural identificada.",
            )

        # ── Extração de entidades comuns ──────────────────────────────────────
        data_inicio, data_fim, period_text = _periodo_from_text(text)
        _ini_def, _fim_def, _lbl_def      = _default_periodo()
        ini  = data_inicio or _ini_def
        fim  = data_fim    or _fim_def
        lbl  = period_text or _lbl_def

        top_n    = self._extract_top_n(text)
        operador = self._extract_operator(text)
        produto  = self._extract_produto_code(text)
        setor    = self._extract_setor(text)
        origem   = self._extract_origem(text)
        recursos = self._extract_recurso(text)

        # ── 4.5. Comparação entre dois períodos ──────────────────────────────
        two_periods = _try_parse_two_periods(text)
        if two_periods and self._COMPARA.search(low):
            ini1, fim1, lbl1, ini2, fim2, lbl2 = two_periods
            if self._LD.search(low):
                comp_metric = "geracao_ld"
            elif self._RANKING_REVISAO.search(low):
                comp_metric = "revisao_kg"
            else:
                comp_metric = "producao_total"
            return InterpretationResult(
                intent="comparacao_periodos", route="sql",
                metric=comp_metric,
                data_inicio=ini1, data_fim=fim1, period_text=lbl1,
                data_inicio2=ini2, data_fim2=fim2, period_text2=lbl2,
                entity_value=operador,
                recursos=recursos,
                confidence=0.88,
                reasoning="Comparação entre dois períodos distintos.",
            )

        # ── 4.7. Perda de material (LD + BAG) ────────────────────────────────
        if self._PERDA.search(low) and not self._RANKING_REVISAO.search(low):
            return InterpretationResult(
                intent="perda_material", route="sql",
                metric="perda_material",
                entity_type="operador" if operador else None,
                entity_value=operador,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem,
                confidence=0.88,
                reasoning="Perda de material (LD + BAG) do período.",
            )

        # ── 5. Listar operadores de um setor ──────────────────────────────────
        if (self._OPERADOR.search(low)
                and (self._LISTA.search(low) or self._QUEM.search(low))
                and not self._LD.search(low)
                and not self._RANKING.search(low)):
            return InterpretationResult(
                intent="list_operadores_revisao", route="sql",
                metric="operadores_revisao",
                setor=setor or "revisao",
                confidence=0.90, reasoning="Listagem de operadores por setor.",
            )

        # ── 6. Ranking de PRODUTO com mais LD ─────────────────────────────────
        if (self._LD.search(low)
                and self._PRODUTO.search(low)
                and (self._QUAL.search(low) or self._RANKING.search(low) or self._TOP.search(low))):
            return InterpretationResult(
                intent="ranking_produtos_ld", route="sql",
                metric="geracao_ld", entity_type="produto",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                top_n=top_n or 5,
                setor=setor, origem=origem,
                confidence=0.90,
                reasoning="Ranking de produtos por geração de LD.",
            )

        # ── 7. Ranking / top N usuários com mais LD ───────────────────────────
        if self._LD.search(low) and (self._RANKING.search(low) or self._TOP.search(low) or self._QUEM.search(low)):
            return InterpretationResult(
                intent="ranking_usuarios_ld", route="sql",
                metric="geracao_ld", entity_type="operador",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                top_n=top_n or 5,
                setor=setor, origem=origem,
                confidence=0.89,
                reasoning="Ranking de operadores por LD.",
            )

        # ── 8. LD do PRÓPRIO usuário ("meu LD", "quanto eu identifiquei") ─────
        # entity_value=None → orchestrator injeta user_name automaticamente
        if self._QUALIDADE_RESUMO.search(low):
            return InterpretationResult(
                intent="resumo_qualidade", route="sql",
                metric="qualidade_material",
                entity_type="operador" if (self._PROPRIO.search(low) or operador) else None,
                entity_value=operador,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem,
                confidence=0.87 if (self._PROPRIO.search(low) or operador) else 0.82,
                reasoning="Resumo da producao por qualidade na V_KARDEX.",
            )

        if self._LD.search(low) and self._PROPRIO.search(low):
            return InterpretationResult(
                intent="geracao_ld_por_operador", route="sql",
                metric="geracao_ld", entity_type="operador",
                entity_value=None,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem,
                confidence=0.88,
                reasoning="LD do próprio usuário autenticado (primeira pessoa).",
            )

        # ── 9. LD por operador específico ou com ação de geração ──────────────
        if self._LD.search(low) and operador:
            return InterpretationResult(
                intent="geracao_ld_por_operador", route="sql",
                metric="geracao_ld", entity_type="operador",
                entity_value=operador,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem,
                unidade_filtro="MT" if self._METROS_UNIDADE.search(low) else None,
                confidence=0.85 if operador else 0.68,
                reasoning="Geração de LD por operador (explícito ou autenticado).",
            )

        # ── 10. LD genérico sem operador — usa usuário autenticado ────────────
        # Exemplo: "LD de abril", "quanto de LD nesse mês", "LD em metros de ontem"
        if self._LD.search(low):
            return InterpretationResult(
                intent="ld_total", route="sql",
                metric="geracao_ld", entity_type=None,
                entity_value=None,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem,
                unidade_filtro="MT" if self._METROS_UNIDADE.search(low) else None,
                confidence=0.78,
                reasoning="LD mencionado sem operador — orchestrator usa usuário autenticado.",
            )

        # ── 10a. Ranking de revisão (STG_APONT_REV_GERAL) ───────────────────
        # Deve vir antes do comparativo/produção para não cair nos patterns genéricos.
        if self._RANKING_REVISAO.search(low):
            return InterpretationResult(
                intent="ranking_revisao", route="sql",
                metric="revisao_kg",
                entity_type="operador" if operador else None,
                entity_value=operador,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                top_n=top_n or 5,
                confidence=0.92,
                reasoning="Ranking de produtividade da revisão (STG_APONT_REV_GERAL).",
            )

        # ── 10b. Metros por minuto ────────────────────────────────────────────
        # Antes do comparativo — evita que "m/min da extrusora 2" caia em comparativo_extrusoras
        if self._METROS_MIN.search(low):
            return InterpretationResult(
                intent="metros_por_minuto", route="sql",
                metric="metros_por_minuto",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                recursos=recursos,
                confidence=0.95,
                reasoning="Consulta de metros por minuto.",
            )

        # ── 10c. KGH — KG por hora ────────────────────────────────────────────
        # Antes do comparativo — evita que "KGH da extrusora 1" caia em comparativo_extrusoras
        if self._KGH.search(low):
            return InterpretationResult(
                intent="kgh", route="sql",
                metric="kgh",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                recursos=recursos,
                confidence=0.95,
                reasoning="Consulta de KG por hora.",
            )

        # ── 10d. Horas trabalhadas ────────────────────────────────────────────
        if self._HORAS.search(low):
            return InterpretationResult(
                intent="horas_trabalhadas", route="sql",
                metric="horas_trabalhadas",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                recursos=recursos,
                confidence=0.93,
                reasoning="Consulta de horas trabalhadas por extrusora.",
            )

        # ── 10e. Comparativo entre extrusoras ────────────────────────────────
        # Guard _OPERADOR: "qual operador mais produziu nas extrusoras" → ranking, não comparativo
        if self._COMPARATIVO.search(low) or (
            self._PRODUCAO.search(low)
            and (self._EXTRUSORA.search(low) or self._EXTRUSORA_REFERENCIA.search(low))
            and not self._QUEM.search(low) and not self._OPERADOR.search(low)
            and not operador
        ):
            # Quando há palavra de comparação explícita (ex: "MAC1 e 2", "MAC1 vs MAC2"),
            # força recursos=None para garantir que ambas as máquinas sejam consultadas.
            # Na branch PRODUCAO+EXTRUSORA sem comparação, mantém o recurso extraído.
            # Se a frase só citar "extrusora/máquina/MAC" genericamente, também consulta ambas.
            comp_recursos = None if self._COMPARATIVO.search(low) else recursos
            return InterpretationResult(
                intent="comparativo_extrusoras", route="sql",
                metric="producao_total",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                recursos=comp_recursos,
                confidence=0.92,
                reasoning="Comparativo de produção entre extrusoras.",
            )

        # ── 11. Ranking de PRODUÇÃO com quem/qual/top ─────────────────────────
        # Deve vir ANTES de producao_por_operador para não capturar "quem mais produziu"
        if self._PRODUCAO.search(low) and (
            self._QUEM.search(low) or self._RANKING.search(low) or self._TOP.search(low)
        ):
            return InterpretationResult(
                intent="ranking_producao_geral", route="sql",
                metric="producao_total", entity_type="operador",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                top_n=top_n or 50,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.86,
                reasoning="Ranking geral de produção por operador.",
            )

        # ── 12. Ranking geral (RANKING/TOP sem LD nem PRODUCAO explícito) ─────
        if self._RANKING.search(low) or self._TOP.search(low):
            return InterpretationResult(
                intent="ranking_producao_geral", route="sql",
                metric="producao_total", entity_type="operador",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                top_n=top_n or 50,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.82,
                reasoning="Ranking geral de produção.",
            )

        # ── 12.5. Produção agrupada por família de produto (top N) ───────────
        if self._FAMILIA_PRODUTO.search(low):
            return InterpretationResult(
                intent="producao_por_familia", route="sql",
                metric="producao_total", entity_type="familia",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                top_n=top_n or 10,
                origem=origem,
                confidence=0.91,
                reasoning="Produção agrupada por família de produto (3 primeiros chars).",
            )

        # ── 12.6. Produção agrupada por produto (todos, sem filtro qualidade) ─
        if self._AGRUP_PRODUTO.search(low):
            return InterpretationResult(
                intent="producao_agrupada_por_produto", route="sql",
                metric="producao_total", entity_type="produto",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                top_n=top_n or 20,
                origem=origem,
                confidence=0.90,
                reasoning="Produção total agrupada por produto (sem filtro qualidade).",
            )

        # ── 13. Produção por produto específico ───────────────────────────────
        if produto and self._PRODUCAO.search(low):
            return InterpretationResult(
                intent="producao_por_produto", route="sql",
                metric="producao_total", entity_type="produto",
                entity_value=produto,
                produto_filtro=produto,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                origem=origem, recursos=recursos,
                confidence=0.87,
                reasoning="Produção de produto específico.",
            )

        # ── 14. Produção por turno ────────────────────────────────────────────
        if self._TURNO.search(low):
            return InterpretationResult(
                intent="producao_por_turno", route="sql",
                metric="producao_total", entity_type="turno",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.88,
                reasoning="Produção agrupada por turno.",
            )

        # ── 15. Produção dia a dia ────────────────────────────────────────────
        # Sem exigir _PRODUCAO — "total de cada dia", "mês a mês" também ativam
        if self._DIA_A_DIA.search(low):
            return InterpretationResult(
                intent="producao_por_dia", route="sql",
                metric="producao_total", entity_type="dia",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.91,
                reasoning="Producao dia a dia.",
            )

        if self._TOTAL.search(low) and not operador:
            return InterpretationResult(
                intent="total_fabrica", route="sql",
                metric="producao_total",
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.85,
                reasoning="Total geral de produção da fábrica.",
            )

        # ── 16. Produção do PRÓPRIO usuário ───────────────────────────────────
        if self._PRODUCAO.search(low) and self._PROPRIO.search(low):
            return InterpretationResult(
                intent="producao_por_operador", route="sql",
                metric="producao_total", entity_type="operador",
                entity_value=None,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.86,
                reasoning="Produção do próprio usuário autenticado (primeira pessoa).",
            )

        # ── 17. Expedição — não implementada ─────────────────────────────────
        if self._EXPEDICAO.search(low):
            return InterpretationResult(
                intent="expedicao_nao_implementada", route="smalltalk",
                confidence=0.90,
                reasoning="Consulta de expedição — funcionalidade ainda não disponível.",
            )

        # ── 17b. Produção sem quem/ranking/operador → total da fábrica ──────────
        # "Qual a produção de hoje?" sem qualificador de ranking ou operador.
        # Confidence alta (0.85) evita que o orchestrator substitua pelo contexto anterior.
        if (self._PRODUCAO.search(low)
                and not self._QUEM.search(low)
                and not self._RANKING.search(low)
                and not self._TOP.search(low)
                and not self._PROPRIO.search(low)
                and not operador):
            return InterpretationResult(
                intent="producao_por_operador", route="sql",
                metric="producao_total", entity_type="operador",
                entity_value=None,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.85,
                reasoning="Produção sem qualificador de ranking ou operador → total da fábrica.",
            )

        # ── 18. Produção por operador específico ──────────────────────────────
        if self._PRODUCAO.search(low) or operador:
            return InterpretationResult(
                intent="producao_por_operador", route="sql",
                metric="producao_total", entity_type="operador",
                entity_value=operador,
                data_inicio=ini, data_fim=fim, period_text=lbl,
                setor=setor, origem=origem, recursos=recursos,
                confidence=0.80 if operador else 0.60,
                reasoning="Produção total por operador.",
            )

        # ── Fallback ──────────────────────────────────────────────────────────
        return InterpretationResult(
            intent="clarify", route="clarify",
            confidence=0.40,
            reasoning="Nenhuma intenção identificada com segurança.",
        )

    # ── Helpers de extração ───────────────────────────────────────────────────

    def _extract_top_n(self, text: str) -> int | None:
        m = _RE_TOP_N.search(text)
        if m:
            return int(m.group(1))
        m2 = re.search(r"\b(\d+)\s+(?:usuário|operador|produto)", text, re.IGNORECASE)
        if m2:
            return int(m2.group(1))
        return None

    def _extract_operator(self, text: str) -> str | None:
        """Extrai login de operador do texto (formato nome.sobrenome ou primeiro nome)."""
        # Padrão nome.sobrenome explícito
        m = _RE_OPERATOR.search(text)
        if m:
            candidate = m.group(1).lower()
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
        for setor_alias in ["extrusora", "expedição", "expedicao", "expedicão", "revisão", "revisao", "producao", "produção"]:
            if setor_alias in low:
                return _normalizar_setor(setor_alias)
        return None

    def _extract_origem(self, text: str) -> str | None:
        """Detecta tipo de movimentação (SD1/SD2/SD3 ou por nome)."""
        low = text.lower()
        for codigo in ORIGENS:
            if codigo.lower() in low:
                return codigo
        if re.search(r"\bentrada\b", low):
            return "SD1"
        if re.search(r"\bsa[íi]da\b", low):
            return "SD2"
        if re.search(r"movimenta[cç][aã]o\s+interna|\binterna\b", low):
            return "SD3"
        return None

    def _extract_produto_code(self, text: str) -> str | None:
        m = _RE_PRODUTO.search(text)
        return m.group(1).upper() if m else None

    def _extract_recurso(self, text: str) -> list[str] | None:
        """
        Detecta referência a extrusora/recurso específico.
        Retorna lista de códigos ou None (padrão = ambas extrusoras no service).
        """
        low = text.lower()
        # Extrusora 1 / MAC1 / Máquina 1 / MAX1 (typo)
        if re.search(r"extrusora\s*1|mac\s*1|m[aá]quina\s*1|max\s*1|\b0003\b", low):
            return ["0003"]
        # Extrusora 2 / MAC2 / Máquina 2 / MAX2 (typo)
        if re.search(r"extrusora\s*2|mac\s*2|m[aá]quina\s*2|max\s*2|\b0007\b", low):
            return ["0007"]
        # Revisão explícita (recursos de revisão)
        if re.search(r"revis[aã]o", low) and not re.search(r"produ[cç][aã]o|extrusora", low):
            return ["0005", "0006"]
        return None
