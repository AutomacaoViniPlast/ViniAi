"""
sql_service_kardex.py — Queries SQL para a view dbo.V_KARDEX no SQL Server (METABASE).

Escopo desta view:
  V_KARDEX representa movimentações de estoque, produção, entradas, saídas e registros
  operacionais relacionados aos materiais da empresa.

  Consultada quando o request envolver: OP, TURNO, TES, qualidade do material
  (Y=LD / I=Inteiro / P=Fora de Padrão), LOTE, FAMILIA, UNIDADE ou detalhamento
  de movimentação.

  Consultas de apontamento de extrusoras (KGH, m/min, ranking de peso) continuam
  sendo atendidas por sql_service_sh6.py (tabela STG_PROD_SH6_VPLONAS).

Colunas da view:
  FILIAL      → empresa (ver FILIAL_MAP)
  ORIGEM      → SD1=Entrada, SD2=Saída, SD3=Movimentação Interna (ver ORIGEM_MAP)
  OP          → Ordem de Produção (gerada pelo PCP)
  EMISSAO     → date — campo principal de filtro por período
  LOCAL       → armazém (ver LOCAL_ARMAZENS_CONHECIDOS — significados pendentes)
  TES         → tipo de movimentação (ver TES_MAP — PENDENTE: detalhamento completo)
  PRODUTO     → código do produto — ver parse_produto()
  DESCRICAO   → descrição completa do material
  TIPO        → PENDENTE: sem regra definida ainda
  UM          → unidade de medida principal: KG | MT
  LOTE        → sequência gerada ao registrar bobina na produção
  QUANTIDADE  → total produzido/movimentado — sempre lido em conjunto com UM
  USUARIO     → operador que registrou o movimento
  LOCAL_OP    → localização operacional (padrão: EXTRUSAO)
               PENDENTE: mapear demais valores de LOCAL_OP
  FAMILIA     → família do produto (3 primeiros chars de PRODUTO) — coluna direta da view
  COR_FRENTE  → cor frente (prioritária sobre inferência do parser)
  COR_MEIO    → cor meio (prioritária sobre inferência do parser)
  COR_VERSO   → cor verso (prioritária sobre inferência do parser)
  TURNO       → turno — filtrado somente quando explicitamente solicitado
  HORA        → hora do apontamento
  QTSEGUM     → segunda quantidade com regra de inversão:
               - Se UM='KG' na linha → QTSEGUM contém metros lineares (MT)
               - Se UM='MT' na linha → QTSEGUM contém KG (inversão obrigatória do sistema)
               Para somar metros de LD/BAG: SUM(QTSEGUM) WHERE UM='KG'
  RECURSO     → extrusora (ver RECURSO_MAP)
  QUALIDADE   → Y=LD, I=Inteiro, P=Fora de Padrão (posição 5 do código PRODUTO)
  USR_LIB_APO → usuário que libera o apontamento quando o lançamento está bloqueado

Regras de query (SQL Server — pyodbc):
  - Parâmetros com ? (nunca %s)
  - Sempre LTRIM(RTRIM(campo)) para remover espaços
  - Case-insensitive: UPPER(col) conforme necessário
  - Paginação: TOP N (não LIMIT)
  - Filial padrão: 010101
  - LOCAL_OP padrão: EXTRUSAO em consultas de produção/soma
  - TURNO filtrado apenas quando o usuário solicitar explicitamente
  - ORIGEM: filtro opcional
  - TES 010: bloqueada — não exposta nem via solicitação direta
  - QUANTIDADE + UM: nunca somar unidades diferentes sem separação explícita
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from app.config import OPERADORES_REVISAO
from app.db import get_mssql_conn


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES E MAPEAMENTOS
# ══════════════════════════════════════════════════════════════════════════════

FILIAL_MAP: dict[str, str] = {
    "010101": "VINIPLAST",
    "010201": "MKTRADING",  # razão social: VINITRADE INDUSTRIA E COMERCIO LTDA
}
FILIAL_PADRAO = "010101"

RECURSO_MAP: dict[str, str] = {
    "0003": "Extrusora 1 (MAC1)",
    "0007": "Extrusora 2 (MAC2)",
}

# Qualidade do material — lida da posição 5 do código PRODUTO ou do campo QUALIDADE da view.
# MSP008 é caso especial (BAG), não segue leitura posicional.
QUALIDADE_MAP: dict[str, str] = {
    "Y":   "LD / Leves Defeitos",
    "I":   "Inteiro",
    "P":   "Fora de Padrão",
    "BAG": "BAG",
}

# TES — tipos de movimentação conhecidos.
# TES 010: existente no banco, sem mapeamento definitivo — bloqueada.
# PENDENTE: detalhamento completo de TES será fornecido pelo usuário.
TES_MAP: dict[str, str] = {
    "499": "Compra sem nota (Entrada)",
    "999": "Venda (Saída)",
    "502": "Venda (Saída)",
    # "010": "Bonificação (Entrada) — bloqueada",
}
TES_ATIVAS: tuple[str, ...] = tuple(TES_MAP.keys())  # ("499", "999", "502")

# Origens com descrição detalhada para exibição amigável.
ORIGEM_MAP: dict[str, dict] = {
    "SD1": {
        "label": "Entrada",
        "descricao": "Itens de notas fiscais de entrada (compra, devolução de venda, transferência recebida)",
    },
    "SD2": {
        "label": "Saída",
        "descricao": "Itens de notas fiscais de saída (vendas, remessas, transferências enviadas)",
    },
    "SD3": {
        "label": "Movimentação Interna",
        "descricao": "Movimentações internas sem NF (requisição, devolução interna, transferência)",
    },
}
ORIGENS_VALIDAS: tuple[str, ...] = tuple(ORIGEM_MAP.keys())

# Unidades de medida válidas para QUANTIDADE e QTSEGUM.
UM_VALIDAS: tuple[str, ...] = ("KG", "MT")

# LOCAL_OP padrão para consultas de produção (extrusão).
# PENDENTE: mapear outros valores de LOCAL_OP além de EXTRUSAO.
LOCAL_OP_PRODUCAO = "EXTRUSAO"

# LOCAL (armazém) — valores identificados no banco, sem mapeamento de significado.
# PENDENTE: o usuário irá detalhar o significado de cada armazém.
LOCAL_ARMAZENS_CONHECIDOS: tuple[str, ...] = (
    "01", "10", "12", "15", "20", "35", "40", "50", "60"
)


# ══════════════════════════════════════════════════════════════════════════════
# PARSER E TRADUTORES
# ══════════════════════════════════════════════════════════════════════════════

def parse_produto(codigo: str) -> dict:
    """
    Interpreta estruturalmente o código do produto conforme regras da view V_KARDEX.

    Estrutura do código (exemplo: CLILA0600L0400A):
      Posições 1–3  → família/código-base           (ex: CLI)
      Posição 5     → qualidade: Y=LD, I=Inteiro, P=Fora de Padrão
      Posições 6–8  → cor frente (inferida)
      Posições 11–13→ cor verso (inferida)

    Caso especial:
      MSP008 → BAG — identificação especial, não segue o padrão posicional.

    IMPORTANTE: quando as colunas COR_FRENTE, COR_MEIO e COR_VERSO estiverem disponíveis
    na query, elas devem ser priorizadas sobre os valores inferidos aqui.

    Retorna estrutura segura (parcial) quando o código for incompleto ou nulo.
    """
    c = (codigo or "").strip()

    # Caso especial: produto BAG
    if c.upper() == "MSP008":
        return {
            "codigo_produto_original": c,
            "familia": "MSP",
            "qualidade_material": "BAG",
            "qualidade_descricao": QUALIDADE_MAP["BAG"],
            "posicao_5_raw": None,
            "cor_frente_inferida": None,
            "cor_meio_inferida": None,   # posição no código não mapeada para este tipo
            "cor_verso_inferida": None,
            "is_bag": True,
        }

    familia = c[0:3] if len(c) >= 3 else (c or None)
    posicao_5 = c[4] if len(c) >= 5 else None
    qualidade_material = posicao_5 if posicao_5 in QUALIDADE_MAP else None
    qualidade_descricao = QUALIDADE_MAP.get(posicao_5) if posicao_5 else None

    return {
        "codigo_produto_original": c,
        "familia": familia,
        "qualidade_material": qualidade_material,    # "Y" | "I" | "P" | None
        "qualidade_descricao": qualidade_descricao,  # ex: "LD / Leves Defeitos" | None
        "posicao_5_raw": posicao_5,
        # Cores inferidas do código — usar colunas COR_FRENTE/COR_MEIO/COR_VERSO quando disponíveis.
        "cor_frente_inferida": c[5:8] if len(c) >= 8 else None,
        "cor_meio_inferida": None,          # posição no código não mapeada — aguarda documentação
        "cor_verso_inferida": c[10:13] if len(c) >= 13 else None,
        "is_bag": False,
    }


def resolve_qualidade_produto(produto: str) -> str | None:
    """Extrai apenas a qualidade do código do produto. Retorna 'Y', 'I', 'P', 'BAG' ou None."""
    return parse_produto(produto)["qualidade_material"]


def resolve_segunda_unidade_por_qualidade(qualidade: str | None) -> str | None:
    """
    Retorna a unidade de medida efetiva para QTSEGUM com base na qualidade do material.

    Regra exclusiva para QTSEGUM (não confundir com QUANTIDADE + UM):
      I / P   → KG
      Y / BAG → MT  (apenas quando UM='KG' na linha — ver regra de inversão no cabeçalho)

    Retorna None quando a qualidade não for reconhecida.
    """
    if qualidade in ("I", "P"):
        return "KG"
    if qualidade in ("Y", "BAG"):
        return "MT"
    return None


def normalize_quantidade_por_unidade(quantidade: float | None, um: str | None) -> dict:
    """
    Retorna a quantidade normalizada junto com sua unidade.
    Nunca mistura unidades — o par (valor, unidade) é sempre retornado junto.
    """
    return {
        "valor": quantidade if quantidade is not None else 0.0,
        "unidade": (um or "").strip().upper() or None,
    }


def traduzir_filial(filial: str) -> str:
    return FILIAL_MAP.get((filial or "").strip(), (filial or "").strip())


def traduzir_recurso(recurso: str) -> str:
    return RECURSO_MAP.get((recurso or "").strip(), (recurso or "").strip())


def traduzir_origem(origem: str) -> str:
    """Retorna o label amigável da origem (ex: 'SD2' → 'Saída')."""
    return ORIGEM_MAP.get((origem or "").strip().upper(), {}).get("label", (origem or "").strip())


def traduzir_qualidade(qualidade: str | None) -> str | None:
    """Retorna a descrição amigável da qualidade (ex: 'Y' → 'LD / Leves Defeitos')."""
    return QUALIDADE_MAP.get((qualidade or "").strip().upper())


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE CLÁUSULAS SQL
# ══════════════════════════════════════════════════════════════════════════════

def _parse_date(date_str: str):
    """Converte string DD/MM/YYYY em datetime.date para pyodbc."""
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()


def _rows_as_dicts(cur) -> list[dict]:
    """Converte resultado do cursor em lista de dicts usando os nomes das colunas."""
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _filial_clause(filial: str | None) -> tuple[str, list]:
    return "AND LTRIM(RTRIM(FILIAL)) = ?", [filial or FILIAL_PADRAO]


def _local_op_clause(local_op: str = LOCAL_OP_PRODUCAO) -> tuple[str, list]:
    # PENDENTE: mapear outros valores de LOCAL_OP além de EXTRUSAO.
    return "AND UPPER(LTRIM(RTRIM(LOCAL_OP))) = UPPER(?)", [local_op]


def _origem_clause(origem: str | None) -> tuple[str, list]:
    if origem and origem.upper() in ORIGENS_VALIDAS:
        return "AND LTRIM(RTRIM(ORIGEM)) = ?", [origem.upper()]
    return "", []


def _recurso_clause(recursos: list[str] | None) -> tuple[str, list]:
    if recursos:
        ph = ", ".join(["?"] * len(recursos))
        return f"AND LTRIM(RTRIM(RECURSO)) IN ({ph})", list(recursos)
    return "", []


def _turno_clause(turno: str | None) -> tuple[str, list]:
    """Turno só é filtrado quando explicitamente solicitado pelo usuário."""
    if turno:
        return "AND UPPER(LTRIM(RTRIM(TURNO))) = UPPER(?)", [turno]
    return "", []


def _tes_clause(tes: str | list[str] | None) -> tuple[str, list]:
    """TES 010 bloqueada — não aceita mesmo se solicitada explicitamente."""
    if tes:
        valores = [tes] if isinstance(tes, str) else list(tes)
        validos = [t for t in valores if t in TES_ATIVAS]
        if validos:
            ph = ", ".join(["?"] * len(validos))
            return f"AND LTRIM(RTRIM(TES)) IN ({ph})", validos
    return "", []


def _qualidade_clause(qualidade: str | list[str] | None) -> tuple[str, list]:
    """Filtro pelo campo QUALIDADE da view (Y, I, P)."""
    if qualidade:
        valores = [qualidade] if isinstance(qualidade, str) else list(qualidade)
        validos = [q.upper() for q in valores if q.upper() in QUALIDADE_MAP]
        if validos:
            ph = ", ".join(["?"] * len(validos))
            return f"AND LTRIM(RTRIM(QUALIDADE)) IN ({ph})", validos
    return "", []


def _op_clause(op: str | None) -> tuple[str, list]:
    if op:
        return "AND LTRIM(RTRIM(OP)) = ?", [op.strip()]
    return "", []


def _lote_clause(lote: str | None) -> tuple[str, list]:
    if lote:
        return "AND LTRIM(RTRIM(LOTE)) = ?", [lote.strip()]
    return "", []


def _local_armazem_clause(local: str | None) -> tuple[str, list]:
    """
    Filtro por LOCAL (armazém).
    PENDENTE: o significado de cada armazém será detalhado pelo usuário.
    """
    if local:
        return "AND LTRIM(RTRIM(LOCAL)) = ?", [local.strip()]
    return "", []


def _familia_clause(familia: str | None) -> tuple[str, list]:
    """Filtro pelo campo FAMILIA da view (3 primeiros chars do produto)."""
    if familia:
        return "AND UPPER(LTRIM(RTRIM(FAMILIA))) = UPPER(?)", [familia.strip()]
    return "", []


def _incluir_clause(usuarios: list[str] | None) -> tuple[str, list]:
    if usuarios:
        ph = ", ".join(["?"] * len(usuarios))
        return f"AND LTRIM(RTRIM(USUARIO)) IN ({ph})", list(usuarios)
    return "", []


def _excluir_clause(usuarios: list[str] | None) -> tuple[str, list]:
    if usuarios:
        ph = ", ".join(["?"] * len(usuarios))
        return f"AND LTRIM(RTRIM(USUARIO)) NOT IN ({ph})", list(usuarios)
    return "", []


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class SQLServiceKardex:
    """
    Executa consultas na view dbo.V_KARDEX e retorna dados estruturados para o orchestrator.

    Regras gerais:
      - Filial padrão: 010101 (VINIPLAST)
      - LOCAL_OP padrão: EXTRUSAO em consultas de produção
      - QUANTIDADE sempre separada por UM — métodos agregados retornam {"KG": ..., "MT": ...}
      - QTSEGUM lida com regra de unidade por qualidade via resolve_segunda_unidade_por_qualidade()
      - COR_FRENTE, COR_MEIO, COR_VERSO priorizadas sobre inferência do parser
      - TES 010 bloqueada em todas as queries
    """

    # ── Produção total por período ────────────────────────────────────────────
    def get_producao_total(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
    ) -> dict[str, Decimal]:
        """
        Soma de QUANTIDADE separada por UM (KG, MT), filtrado por LOCAL_OP=EXTRUSAO.
        Retorna {"KG": Decimal(...), "MT": Decimal(...)}.
        """
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause()
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT LTRIM(RTRIM(UM)) AS unidade, COALESCE(SUM(QUANTIDADE), 0) AS total
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {fil_sql}
              {loc_sql}
              {rec_sql}
              {ori_sql}
            GROUP BY LTRIM(RTRIM(UM))
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + rec_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            resultado = {um: Decimal("0") for um in UM_VALIDAS}
            for row in cur.fetchall():
                um = (row[0] or "").strip().upper()
                if um in resultado:
                    resultado[um] = Decimal(str(row[1]))
            return resultado

    # ── Produção por operador ─────────────────────────────────────────────────
    def get_producao_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
    ) -> dict[str, Decimal]:
        """Soma de QUANTIDADE por UM para um operador específico."""
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause()
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT LTRIM(RTRIM(UM)) AS unidade, COALESCE(SUM(QUANTIDADE), 0) AS total
            FROM dbo.V_KARDEX
            WHERE LOWER(LTRIM(RTRIM(USUARIO))) LIKE LOWER(?)
              AND EMISSAO BETWEEN ? AND ?
              {fil_sql}
              {loc_sql}
              {rec_sql}
              {ori_sql}
            GROUP BY LTRIM(RTRIM(UM))
        """
        params = [f"%{operador.strip()}%", _parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + rec_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            resultado = {um: Decimal("0") for um in UM_VALIDAS}
            for row in cur.fetchall():
                um = (row[0] or "").strip().upper()
                if um in resultado:
                    resultado[um] = Decimal(str(row[1]))
            return resultado

    # ── LD por operador ───────────────────────────────────────────────────────
    def get_ld_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        origem: str | None = None,
    ) -> dict[str, Decimal]:
        """
        KG → SUM(QUANTIDADE) WHERE UM='KG'
        MT → SUM(QTSEGUM)    WHERE UM='KG'
             (quando UM='MT' o QTSEGUM representa KG — inversão do sistema — excluído da soma de metros)

        PENDÊNCIA (Bug 13): raul.ribeiro pode não aparecer quando o campo USUARIO
        usa formato diferente (ex: "RAUL" sem sobrenome). Investigar normalização
        do campo USUARIO na V_KARDEX antes de corrigir.
        """
        fil_sql, fil_p = _filial_clause(filial)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT
                COALESCE(SUM(COALESCE(PESO_KG, 0)), 0) AS total_kg,
                COALESCE(SUM(CASE WHEN UPPER(LTRIM(RTRIM(UM))) = 'KG' THEN COALESCE(QTSEGUM, 0) ELSE 0 END), 0) AS total_mt
            FROM dbo.V_KARDEX
            WHERE LOWER(LTRIM(RTRIM(USUARIO))) LIKE LOWER(?)
              AND EMISSAO BETWEEN ? AND ?
              AND LTRIM(RTRIM(QUALIDADE)) = 'Y'
              {fil_sql}
              {ori_sql}
        """
        params = [f"%{operador.strip()}%", _parse_date(data_inicio), _parse_date(data_fim)] + fil_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return {
                "KG": Decimal(str(row[0] or 0)),
                "MT": Decimal(str(row[1] or 0)),
            }

    # ── Ranking de LD por operador ────────────────────────────────────────────
    def get_ranking_ld(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        unidade: str = "KG",
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
        excluir_usuarios: list[str] | None = None,
    ) -> list[dict]:
        """
        Ranking de operadores por quantidade de LD (QUALIDADE='Y').
        O parâmetro `unidade` garante que o ranking compare grandezas equivalentes (KG ou MT).
        """
        fil_sql, fil_p = _filial_clause(filial)
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        excl_sql, excl_p = _excluir_clause(excluir_usuarios)
        um_filtrado = (unidade or "KG").upper()

        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(USUARIO)) AS operador,
                SUM(QUANTIDADE)       AS total
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND LTRIM(RTRIM(QUALIDADE)) = 'Y'
              AND UPPER(LTRIM(RTRIM(UM))) = ?
              {fil_sql}
              {rec_sql}
              {ori_sql}
              {incl_sql}
              {excl_sql}
            GROUP BY LTRIM(RTRIM(USUARIO))
            ORDER BY total DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim), um_filtrado] + fil_p + rec_p + ori_p + incl_p + excl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "posicao": i + 1,
                    "operador": r[0],
                    "total": float(r[1]),
                    "unidade": um_filtrado,
                }
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Ranking de produtos com mais LD ──────────────────────────────────────
    def get_ranking_produtos_ld(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        unidade: str = "KG",
        filial: str | None = None,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> list[dict]:
        fil_sql, fil_p = _filial_clause(filial)
        ori_sql, ori_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        um_filtrado = (unidade or "KG").upper()

        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(PRODUTO))          AS produto,
                MAX(LTRIM(RTRIM(DESCRICAO)))   AS descricao,
                MAX(LTRIM(RTRIM(FAMILIA)))     AS familia,
                MAX(LTRIM(RTRIM(COR_FRENTE)))  AS cor_frente,
                MAX(LTRIM(RTRIM(COR_MEIO)))    AS cor_meio,
                MAX(LTRIM(RTRIM(COR_VERSO)))   AS cor_verso,
                SUM(QUANTIDADE)                AS total,
                COUNT(*)                       AS ocorrencias
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND LTRIM(RTRIM(QUALIDADE)) = 'Y'
              AND UPPER(LTRIM(RTRIM(UM))) = ?
              {fil_sql}
              {ori_sql}
              {incl_sql}
            GROUP BY LTRIM(RTRIM(PRODUTO))
            ORDER BY total DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim), um_filtrado] + fil_p + ori_p + incl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()
            return [
                {
                    "posicao": i + 1,
                    "produto": r[0],
                    "descricao": r[1],
                    # Coluna FAMILIA da view tem prioridade; fallback para inferência do parser.
                    "familia": r[2] or parse_produto(r[0])["familia"],
                    "cor_frente": r[3],
                    "cor_meio": r[4],
                    "cor_verso": r[5],
                    "total": float(r[6]),
                    "unidade": um_filtrado,
                    "ocorrencias": int(r[7]),
                    "parsed_produto": parse_produto(r[0]),
                }
                for i, r in enumerate(rows)
            ]

    # ── Produção por turno ────────────────────────────────────────────────────
    def get_producao_por_turno(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> list[dict]:
        """
        Agrega QUANTIDADE por TURNO e UM.
        Sempre aplica LOCAL_OP=EXTRUSAO — turno só é relevante em contexto de produção.
        """
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause()
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)

        query = f"""
            SELECT
                LTRIM(RTRIM(TURNO)) AS turno,
                LTRIM(RTRIM(UM))    AS unidade,
                SUM(QUANTIDADE)     AS total,
                COUNT(*)            AS registros
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {fil_sql}
              {loc_sql}
              {rec_sql}
              {ori_sql}
              {incl_sql}
            GROUP BY LTRIM(RTRIM(TURNO)), LTRIM(RTRIM(UM))
            ORDER BY turno, unidade
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + rec_p + ori_p + incl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "turno": r[0],
                    "unidade": r[1],
                    "total": float(r[2]) if r[2] is not None else 0.0,
                    "registros": int(r[3]),
                }
                for r in cur.fetchall()
            ]

    # ── Movimentações filtradas por TES ──────────────────────────────────────
    def get_movimentacao_por_tes(
        self,
        data_inicio: str,
        data_fim: str,
        tes: str | list[str] | None = None,
        filial: str | None = None,
        origem: str | None = None,
        limite: int = 50,
    ) -> list[dict]:
        """
        Retorna registros de movimentação filtrados por TES.
        TES 010 bloqueada — não será incluída mesmo se solicitada.
        PENDENTE: tratamento de sinal de QUANTIDADE para TES 999 (saída com valor negativo).
        PENDENTE: regras completas de TES serão detalhadas pelo usuário.
        """
        fil_sql, fil_p = _filial_clause(filial)
        tes_sql, tes_p = _tes_clause(tes)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT TOP {limite}
                EMISSAO                          AS emissao,
                LTRIM(RTRIM(HORA))               AS hora,
                LTRIM(RTRIM(TES))                AS tes,
                LTRIM(RTRIM(PRODUTO))            AS produto,
                LTRIM(RTRIM(DESCRICAO))          AS descricao,
                LTRIM(RTRIM(FAMILIA))            AS familia,
                LTRIM(RTRIM(QUALIDADE))          AS qualidade,
                QUANTIDADE                       AS quantidade,
                LTRIM(RTRIM(UM))                 AS um,
                QTSEGUM                          AS qtsegum,
                LTRIM(RTRIM(LOTE))               AS lote,
                LTRIM(RTRIM(USUARIO))            AS usuario,
                LTRIM(RTRIM(USR_LIB_APO))        AS usr_lib_apo,
                LTRIM(RTRIM(COR_FRENTE))         AS cor_frente,
                LTRIM(RTRIM(COR_MEIO))           AS cor_meio,
                LTRIM(RTRIM(COR_VERSO))          AS cor_verso,
                LTRIM(RTRIM(TIPO))               AS tipo
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {fil_sql}
              {tes_sql}
              {ori_sql}
            ORDER BY EMISSAO DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + tes_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = _rows_as_dicts(cur)
        return [_enriquecer_registro(r) for r in rows]

    # ── Consulta por lote ─────────────────────────────────────────────────────
    def get_por_lote(
        self,
        lote: str,
        filial: str | None = None,
    ) -> list[dict]:
        """Retorna todos os registros de um lote para rastreabilidade completa da bobina."""
        fil_sql, fil_p = _filial_clause(filial)

        query = f"""
            SELECT
                EMISSAO                          AS emissao,
                LTRIM(RTRIM(HORA))               AS hora,
                LTRIM(RTRIM(TES))                AS tes,
                LTRIM(RTRIM(PRODUTO))            AS produto,
                LTRIM(RTRIM(DESCRICAO))          AS descricao,
                LTRIM(RTRIM(FAMILIA))            AS familia,
                LTRIM(RTRIM(QUALIDADE))          AS qualidade,
                QUANTIDADE                       AS quantidade,
                LTRIM(RTRIM(UM))                 AS um,
                QTSEGUM                          AS qtsegum,
                LTRIM(RTRIM(LOTE))               AS lote,
                LTRIM(RTRIM(USUARIO))            AS usuario,
                LTRIM(RTRIM(USR_LIB_APO))        AS usr_lib_apo,
                LTRIM(RTRIM(TURNO))              AS turno,
                LTRIM(RTRIM(RECURSO))            AS recurso,
                LTRIM(RTRIM(COR_FRENTE))         AS cor_frente,
                LTRIM(RTRIM(COR_MEIO))           AS cor_meio,
                LTRIM(RTRIM(COR_VERSO))          AS cor_verso,
                LTRIM(RTRIM(TIPO))               AS tipo
            FROM dbo.V_KARDEX
            WHERE LTRIM(RTRIM(LOTE)) = ?
              {fil_sql}
            ORDER BY EMISSAO DESC
        """
        params = [lote.strip()] + fil_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = _rows_as_dicts(cur)
        return [_enriquecer_registro(r) for r in rows]

    # ── Consulta por OP ───────────────────────────────────────────────────────
    def get_por_op(
        self,
        op: str,
        data_inicio: str | None = None,
        data_fim: str | None = None,
        filial: str | None = None,
        limite: int = 100,
    ) -> list[dict]:
        """
        Retorna registros associados a uma Ordem de Produção.
        Período é opcional — útil para OPs com registros em múltiplas datas.
        """
        fil_sql, fil_p = _filial_clause(filial)
        op_sql, op_p = _op_clause(op)

        periodo_sql = ""
        periodo_p: list = []
        if data_inicio and data_fim:
            periodo_sql = "AND EMISSAO BETWEEN ? AND ?"
            periodo_p = [_parse_date(data_inicio), _parse_date(data_fim)]

        query = f"""
            SELECT TOP {limite}
                EMISSAO                          AS emissao,
                LTRIM(RTRIM(HORA))               AS hora,
                LTRIM(RTRIM(OP))                 AS op,
                LTRIM(RTRIM(TES))                AS tes,
                LTRIM(RTRIM(PRODUTO))            AS produto,
                LTRIM(RTRIM(DESCRICAO))          AS descricao,
                LTRIM(RTRIM(FAMILIA))            AS familia,
                LTRIM(RTRIM(QUALIDADE))          AS qualidade,
                QUANTIDADE                       AS quantidade,
                LTRIM(RTRIM(UM))                 AS um,
                QTSEGUM                          AS qtsegum,
                LTRIM(RTRIM(LOTE))               AS lote,
                LTRIM(RTRIM(USUARIO))            AS usuario,
                LTRIM(RTRIM(USR_LIB_APO))        AS usr_lib_apo,
                LTRIM(RTRIM(TURNO))              AS turno,
                LTRIM(RTRIM(RECURSO))            AS recurso,
                LTRIM(RTRIM(COR_FRENTE))         AS cor_frente,
                LTRIM(RTRIM(COR_MEIO))           AS cor_meio,
                LTRIM(RTRIM(COR_VERSO))          AS cor_verso
            FROM dbo.V_KARDEX
            WHERE 1=1
              {op_sql}
              {fil_sql}
              {periodo_sql}
            ORDER BY EMISSAO DESC
        """
        params = op_p + fil_p + periodo_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = _rows_as_dicts(cur)
        return [_enriquecer_registro(r) for r in rows]

    # ── Total de LD (sem filtro de operador) ─────────────────────────────────
    def get_ld_total(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> dict[str, Decimal]:
        """
        KG → SUM(QUANTIDADE) WHERE UM='KG'
        MT → SUM(QTSEGUM)    WHERE UM='KG'
             (quando UM='MT' o QTSEGUM representa KG — inversão do sistema — excluído da soma de metros)

        Usado quando nenhum operador específico for solicitado.
        """
        fil_sql, fil_p = _filial_clause(filial)
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)

        query = f"""
            SELECT
                COALESCE(SUM(COALESCE(PESO_KG, 0)), 0) AS total_kg,
                COALESCE(SUM(CASE WHEN UPPER(LTRIM(RTRIM(UM))) = 'KG' THEN COALESCE(QTSEGUM, 0) ELSE 0 END), 0) AS total_mt
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND LTRIM(RTRIM(QUALIDADE)) = 'Y'
              {fil_sql}
              {rec_sql}
              {ori_sql}
              {incl_sql}
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + rec_p + ori_p + incl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return {
                "KG": Decimal(str(row[0] or 0)),
                "MT": Decimal(str(row[1] or 0)),
            }

    # ── Resumo de produção por qualidade (Inteiro / LD / FP) ────────────────
    def get_resumo_qualidade(
        self,
        data_inicio: str,
        data_fim: str,
        operador: str | None = None,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> dict[str, dict[str, Decimal]]:
        """
        Agrega QUANTIDADE por QUALIDADE e UM — mesma lógica de get_ld_total,
        estendida para todas as qualidades (I, Y, P, BAG).

        Retorna estrutura:
          {"I": {"KG": Decimal, "MT": Decimal},
           "Y": {"KG": Decimal, "MT": Decimal},
           "P": {"KG": Decimal, "MT": Decimal},
           "BAG": {"KG": Decimal, "MT": Decimal}}

        PENDENTE: confirmar coluna correta de KG para Inteiro/P/BAG —
        se o resultado vier zerado, rodar query diagnóstica no banco.
        """
        fil_sql, fil_p = _filial_clause(filial)
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)

        op_sql: str = ""
        op_p: list = []
        if operador:
            op_sql = "AND LOWER(LTRIM(RTRIM(USUARIO))) LIKE LOWER(?)"
            op_p = [f"%{operador.strip()}%"]

        incl_sql, incl_p = "", []
        if filtro_usuarios and not operador:
            incl_sql, incl_p = _incluir_clause(filtro_usuarios)

        # BAG = PRODUTO='MSP008' (independente de QUALIDADE)
        # I=Inteiro, Y=LD, P=Fora de Padrão — via coluna QUALIDADE
        # KG: usa PESO_KG da view (já encapsula: UM='KG'→QUANTIDADE, UM='MT'→QTSEGUM)
        # MT: SUM(QTSEGUM WHERE UM='KG') — exclui UM='MT' pois nesse caso QTSEGUM=KG (inversão)
        query = f"""
            SELECT
                CASE
                    WHEN UPPER(LTRIM(RTRIM(PRODUTO))) = 'MSP008' THEN 'BAG'
                    ELSE UPPER(LTRIM(RTRIM(QUALIDADE)))
                END AS qualidade,
                COALESCE(SUM(COALESCE(PESO_KG, 0)), 0) AS total_kg,
                COALESCE(SUM(
                    CASE WHEN UPPER(LTRIM(RTRIM(UM))) = 'KG'
                         THEN COALESCE(QTSEGUM, 0) ELSE 0 END
                ), 0) AS total_mt
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND (
                  UPPER(LTRIM(RTRIM(PRODUTO))) = 'MSP008'
                  OR (
                      UPPER(LTRIM(RTRIM(QUALIDADE))) IN ('I', 'Y', 'P')
                      AND UPPER(LTRIM(RTRIM(PRODUTO))) NOT LIKE 'MSP%'
                  )
              )
              {op_sql}
              {fil_sql}
              {rec_sql}
              {ori_sql}
              {incl_sql}
            GROUP BY
                CASE
                    WHEN UPPER(LTRIM(RTRIM(PRODUTO))) = 'MSP008' THEN 'BAG'
                    ELSE UPPER(LTRIM(RTRIM(QUALIDADE)))
                END
        """
        params = (
            [_parse_date(data_inicio), _parse_date(data_fim)]
            + op_p + fil_p + rec_p + ori_p + incl_p
        )

        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            resultado: dict[str, dict[str, Decimal]] = {
                q: {"KG": Decimal("0"), "MT": Decimal("0")}
                for q in ("I", "Y", "P", "BAG")
            }
            for row in cur.fetchall():
                qualidade = (row[0] or "").strip().upper()
                if qualidade in resultado:
                    resultado[qualidade]["KG"] = Decimal(str(row[1]))
                    resultado[qualidade]["MT"] = Decimal(str(row[2]))
            return resultado

    # ── Produção agrupada por produto (todos, sem filtro qualidade) ─────────
    def get_producao_por_produto(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 20,
        filial: str | None = None,
        origem: str | None = None,
    ) -> list[dict]:
        """
        Soma QUANTIDADE (UM=KG) agrupada por PRODUTO, sem filtro de qualidade.
        Retorna todos os produtos ordenados por total desc.
        """
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause()
        ori_sql, ori_p = _origem_clause(origem)

        # Filtro: somente produtos em bobina — códigos de 12+ caracteres.
        # Códigos curtos (6 chars) são materiais auxiliares que entrarão em outra query:
        # PENDÊNCIA: MSP003=AMARRADO, MSP004=A PICOTAR, MSP006=BORRA,
        #            MTL015=TECIDO, MIS*=materiais internos — validar inclusão futura.
        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(PRODUTO))        AS produto,
                MAX(LTRIM(RTRIM(DESCRICAO))) AS descricao,
                MAX(LTRIM(RTRIM(FAMILIA)))   AS familia,
                SUM(QUANTIDADE)              AS total_kg,
                COUNT(*)                     AS registros
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND UPPER(LTRIM(RTRIM(UM))) = 'KG'
              AND LEN(LTRIM(RTRIM(PRODUTO))) >= 12
              {fil_sql}
              {loc_sql}
              {ori_sql}
            GROUP BY LTRIM(RTRIM(PRODUTO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "posicao":    i + 1,
                    "produto":    r[0] or "",
                    "descricao":  r[1] or "",
                    "familia":    r[2] or "",
                    "total_kg":   float(r[3]) if r[3] else 0.0,
                    "registros":  int(r[4]),
                }
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Produção agrupada por família (3 primeiros chars do produto) ─────────
    def get_producao_por_familia(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 10,
        filial: str | None = None,
        origem: str | None = None,
    ) -> list[dict]:
        """
        Soma QUANTIDADE (UM=KG) agrupada por FAMILIA (3 primeiros chars de PRODUTO).
        Retorna top N famílias ordenadas por total desc.
        """
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause()
        ori_sql, ori_p = _origem_clause(origem)

        # Mesmo critério de get_producao_por_produto: somente bobinas (código >= 12 chars).
        # PENDÊNCIA: famílias MSP, MTL, MIS (auxiliares) excluídas via filtro de comprimento.
        query = f"""
            SELECT TOP {limite}
                UPPER(LTRIM(RTRIM(FAMILIA))) AS familia,
                SUM(QUANTIDADE)              AS total_kg,
                COUNT(*)                     AS registros
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND UPPER(LTRIM(RTRIM(UM))) = 'KG'
              AND LEN(LTRIM(RTRIM(PRODUTO))) >= 12
              AND LTRIM(RTRIM(FAMILIA)) IS NOT NULL
              AND LTRIM(RTRIM(FAMILIA)) <> ''
              {fil_sql}
              {loc_sql}
              {ori_sql}
            GROUP BY UPPER(LTRIM(RTRIM(FAMILIA)))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "posicao":   i + 1,
                    "familia":   r[0] or "",
                    "total_kg":  float(r[1]) if r[1] else 0.0,
                    "registros": int(r[2]),
                }
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Períodos disponíveis no banco ─────────────────────────────────────────
    def get_periodos_disponiveis(self) -> list[dict]:
        """Retorna anos e meses com registros agrupados por ano."""
        query = """
            SELECT YEAR(EMISSAO) AS ano, MONTH(EMISSAO) AS mes
            FROM dbo.V_KARDEX WITH (NOLOCK)
            WHERE EMISSAO IS NOT NULL
            GROUP BY YEAR(EMISSAO), MONTH(EMISSAO)
            ORDER BY ano, mes
        """
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query)
            anos: dict[int, list[int]] = {}
            for r in cur.fetchall():
                ano, mes = int(r[0]), int(r[1])
                anos.setdefault(ano, []).append(mes)
            return [{"ano": ano, "meses": meses} for ano, meses in sorted(anos.items())]


# ══════════════════════════════════════════════════════════════════════════════
# HELPER INTERNO — ENRIQUECIMENTO DE REGISTRO DETALHADO
# ══════════════════════════════════════════════════════════════════════════════

def _enriquecer_registro(r: dict) -> dict:
    """
    Aplica tradutores e resolve metadados derivados em registros detalhados.
    Recebe dict com nomes de colunas em lowercase (gerado por _rows_as_dicts).

    Prioridade das cores:
      COR_FRENTE, COR_MEIO, COR_VERSO da view são definitivas.
      Os campos cor_*_inferida do parser servem como fallback quando a coluna vier nula.
    """
    qualidade = (r.get("qualidade") or "").strip().upper() or None
    produto = r.get("produto") or ""
    parsed = parse_produto(produto)
    quantidade = r.get("quantidade")
    um = (r.get("um") or "").strip().upper() or None
    qtsegum = r.get("qtsegum")

    return {
        **r,
        "emissao": str(r["emissao"]) if r.get("emissao") is not None else None,
        "tes_descricao": TES_MAP.get((r.get("tes") or "").strip()),
        "qualidade_descricao": traduzir_qualidade(qualidade),
        "recurso_label": traduzir_recurso(r["recurso"]) if r.get("recurso") else None,
        "quantidade_normalizada": normalize_quantidade_por_unidade(
            float(quantidade) if quantidade is not None else None, um
        ),
        "qtsegum_unidade_efetiva": resolve_segunda_unidade_por_qualidade(qualidade),
        "qtsegum_normalizado": normalize_quantidade_por_unidade(
            float(qtsegum) if qtsegum is not None else None,
            resolve_segunda_unidade_por_qualidade(qualidade),
        ),
        "parsed_produto": parsed,
    }
