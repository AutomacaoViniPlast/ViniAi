"""
sql_service_kardex.py — Queries SQL para a view dbo.V_KARDEX no SQL Server (METABASE).

Escopo desta view:
  V_KARDEX representa movimentações de materiais relacionadas à produção, revisão
  e movimentação interna. É consultada quando a request envolver: OP, TURNO, TES,
  qualidade do material (Y=LD / I=Inteiro), lote, ou detalhamento de movimentação.

  Consultas de apontamento de extrusoras (KGH, m/min, ranking de peso) continuam
  sendo atendidas por sql_service_sh6.py (tabela STG_PROD_SH6_VPLONAS).

Colunas da view:
  FILIAL      → empresa (ver FILIAL_MAP)
  ORIGEM      → SD1, SD2, SD3 — filtro opcional
  EMISSAO     → date — campo principal de filtro por período
  TES         → tipo de movimentação (ver TES_MAP)
  PRODUTO     → código do produto — ver parse_produto()
  DESCRICAO   → descrição completa do material
  LOTE        → sequência gerada ao lançar bobina na produção
  QUANTIDADE  → total produzido/movimentado
                PENDENTE: TES 999 (saída) retorna valores negativos — confirmar
                lógica de sinal e tratamento de saldo antes de implementar
  USUARIO     → operador que registrou o movimento
  LOCAL_OP    → localização de operação. Valor atual mapeado: 'EXTRUSAO' (produção)
                PENDENTE: mapear demais valores de LOCAL_OP
  TURNO       → turno — filtrado somente quando explicitamente solicitado
  RECURSO     → extrusora (ver RECURSO_MAP)
  QUALIDADE   → Y=LD, I=Inteiro (equivalente à posição 5 do código PRODUTO)

Regras de query (SQL Server — pyodbc):
  - Parâmetros com ? (nunca %s)
  - Sempre LTRIM(RTRIM(campo)) para remover espaços
  - Case-insensitive: UPPER(col) ou LOWER(col) conforme convenção do campo
  - Paginação: TOP N (não LIMIT)
  - Filtro de filial é sempre aplicado (padrão: 010101)
  - LOCAL_OP é aplicado em todas as consultas de produção/soma
  - Filtro por TURNO somente quando o usuário solicitar explicitamente
  - Filtro por ORIGEM é opcional
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from app.db import get_mssql_conn


# ── Constantes e Mapeamentos ──────────────────────────────────────────────────

FILIAL_MAP: dict[str, str] = {
    "010101": "VINIPLAST",
    "010201": "VINITRADE INDUSTRIA E COMERCIO LTDA",
}
FILIAL_PADRAO = "010101"

RECURSO_MAP: dict[str, str] = {
    "0003": "Extrusora 1 (MAC1)",
    "0007": "Extrusora 2 (MAC2)",
}

# TES — Tipos de entrada/saída conhecidos
# TES 010: existente no banco, mas sem mapeamento definitivo — mantida comentada
TES_MAP: dict[str, str] = {
    "499": "Movimentação interna de entrada (entrada de estoque)",
    "999": "Movimentação interna de saída",
    "502": "Inconsistência XML — dados da nota não batem com a chave do XML (CNPJ, IE, Data, Modelo, Série, Número ou Tipo Emissão)",
    # "010": "— significado pendente de mapeamento —",
}
TES_ATIVAS: tuple[str, ...] = tuple(TES_MAP.keys())  # ("499", "999", "502")

# LOCAL_OP para consultas de produção (extrusão)
# PENDENTE: mapear outros valores de LOCAL_OP além de EXTRUSAO
LOCAL_OP_PRODUCAO = "EXTRUSAO"

# Origens conhecidas — filtro opcional
ORIGENS_VALIDAS: tuple[str, ...] = ("SD1", "SD2", "SD3")


# ── Parser de produto ─────────────────────────────────────────────────────────

def parse_produto(codigo: str) -> dict:
    """
    Interpreta o código do produto conforme regra da view V_KARDEX.

    Estrutura do código (exemplo: CLILA0600L0400A):
      Posições 1-3  → código-base do produto          (ex: CLI)
      Posição 5     → tipo de material: Y=LD, I=Inteiro
      Posições 6-8  → cor 1                            (ex: A06)
      Posições 11-13 → cor 2                           (ex: 040)

    Pontos de extensão futuros (não implementados ainda):
      - Significado dos códigos-base (CLI, SUF, etc.) — aguarda documentação
      - Variedades e variações de cor além das posições definidas
    """
    c = (codigo or "").strip()
    codigo_base = c[0:3] if len(c) >= 3 else c
    posicao_5 = c[4] if len(c) >= 5 else None
    tipo_material = "LD" if posicao_5 == "Y" else ("INTEIRO" if posicao_5 == "I" else None)
    cor_1 = c[5:8] if len(c) >= 8 else None
    cor_2 = c[10:13] if len(c) >= 13 else None

    return {
        "codigo_raw": c,
        "codigo_base": codigo_base,
        "tipo_material": tipo_material,   # "LD" | "INTEIRO" | None
        "posicao_5_raw": posicao_5,       # "Y" | "I" | None
        "cor_1": cor_1,
        "cor_2": cor_2,
    }


def traduzir_recurso(recurso: str) -> str:
    return RECURSO_MAP.get((recurso or "").strip(), (recurso or "").strip())


def traduzir_filial(filial: str) -> str:
    return FILIAL_MAP.get((filial or "").strip(), (filial or "").strip())


# ── Helpers internos de cláusula SQL ─────────────────────────────────────────

def _parse_date(date_str: str):
    """Converte string DD/MM/YYYY em datetime.date para pyodbc."""
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()


def _filial_clause(filial: str | None) -> tuple[str, list]:
    """Filial padrão 010101 quando não especificada."""
    return "AND LTRIM(RTRIM(FILIAL)) = ?", [filial or FILIAL_PADRAO]


def _local_op_clause(local_op: str = LOCAL_OP_PRODUCAO) -> tuple[str, list]:
    """
    Filtro de LOCAL_OP para consultas de produção.
    Usa UPPER() para comparação segura independente de capitalização no banco.
    PENDENTE: mapear outros valores de LOCAL_OP além de EXTRUSAO.
    """
    return "AND UPPER(LTRIM(RTRIM(LOCAL_OP))) = UPPER(?)", [local_op]


def _origem_clause(origem: str | None) -> tuple[str, list]:
    """Filtro opcional por origem (SD1, SD2, SD3)."""
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
    """
    Filtro por TES. Aceita string única ou lista.
    Apenas TES mapeadas em TES_ATIVAS são aceitas (TES 010 bloqueada).
    """
    if tes:
        valores = [tes] if isinstance(tes, str) else list(tes)
        validos = [t for t in valores if t in TES_ATIVAS]
        if validos:
            ph = ", ".join(["?"] * len(validos))
            return f"AND LTRIM(RTRIM(TES)) IN ({ph})", validos
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


# ── Service ───────────────────────────────────────────────────────────────────

class SQLServiceKardex:
    """Executa consultas na view dbo.V_KARDEX e retorna dados brutos para o orchestrator."""

    # ── Produção total por período ────────────────────────────────────────────
    def get_producao_total(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
    ) -> Decimal:
        """
        Soma de QUANTIDADE filtrado por LOCAL_OP=EXTRUSAO.
        Retorna o total de material produzido no período.
        """
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause(LOCAL_OP_PRODUCAO)
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT COALESCE(SUM(QUANTIDADE), 0)
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {fil_sql}
              {loc_sql}
              {rec_sql}
              {ori_sql}
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + rec_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Produção por operador ─────────────────────────────────────────────────
    def get_producao_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
    ) -> Decimal:
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause(LOCAL_OP_PRODUCAO)
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT COALESCE(SUM(QUANTIDADE), 0)
            FROM dbo.V_KARDEX
            WHERE LOWER(LTRIM(RTRIM(USUARIO))) LIKE LOWER(?)
              AND EMISSAO BETWEEN ? AND ?
              {fil_sql}
              {loc_sql}
              {rec_sql}
              {ori_sql}
        """
        params = [f"%{operador.strip()}%", _parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + rec_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── LD por operador ───────────────────────────────────────────────────────
    def get_ld_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        origem: str | None = None,
    ) -> Decimal:
        fil_sql, fil_p = _filial_clause(filial)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT COALESCE(SUM(QUANTIDADE), 0)
            FROM dbo.V_KARDEX
            WHERE LOWER(LTRIM(RTRIM(USUARIO))) LIKE LOWER(?)
              AND EMISSAO BETWEEN ? AND ?
              AND QUALIDADE = 'Y'
              {fil_sql}
              {ori_sql}
        """
        params = [f"%{operador.strip()}%", _parse_date(data_inicio), _parse_date(data_fim)] + fil_p + ori_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Ranking de LD por operador ────────────────────────────────────────────
    def get_ranking_ld(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        filial: str | None = None,
        recursos: list[str] | None = None,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
        excluir_usuarios: list[str] | None = None,
    ) -> list[dict]:
        """Ranking de operadores por quantidade de LD (QUALIDADE = 'Y')."""
        fil_sql, fil_p = _filial_clause(filial)
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        excl_sql, excl_p = _excluir_clause(excluir_usuarios)

        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(USUARIO)) AS operador,
                SUM(QUANTIDADE)       AS total_kg
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND QUALIDADE = 'Y'
              {fil_sql}
              {rec_sql}
              {ori_sql}
              {incl_sql}
              {excl_sql}
            GROUP BY LTRIM(RTRIM(USUARIO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + rec_p + ori_p + incl_p + excl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {"posicao": i + 1, "operador": r[0], "total_kg": float(r[1])}
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Ranking de produtos com mais LD ──────────────────────────────────────
    def get_ranking_produtos_ld(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        filial: str | None = None,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> list[dict]:
        fil_sql, fil_p = _filial_clause(filial)
        ori_sql, ori_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)

        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(PRODUTO))             AS produto,
                MAX(LTRIM(RTRIM(DESCRICAO)))      AS descricao,
                SUM(QUANTIDADE)                   AS total_kg,
                COUNT(*)                          AS ocorrencias
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND QUALIDADE = 'Y'
              {fil_sql}
              {ori_sql}
              {incl_sql}
            GROUP BY LTRIM(RTRIM(PRODUTO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + ori_p + incl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "posicao": i + 1,
                    "produto": r[0],
                    "descricao": r[1],
                    "total_kg": float(r[2]),
                    "ocorrencias": int(r[3]),
                    "parsed": parse_produto(r[0]),
                }
                for i, r in enumerate(cur.fetchall())
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
        Agrega QUANTIDADE por TURNO.
        Sempre aplica LOCAL_OP=EXTRUSAO — turno só é relevante em contexto de produção.
        """
        fil_sql, fil_p = _filial_clause(filial)
        loc_sql, loc_p = _local_op_clause(LOCAL_OP_PRODUCAO)
        rec_sql, rec_p = _recurso_clause(recursos)
        ori_sql, ori_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)

        query = f"""
            SELECT
                LTRIM(RTRIM(TURNO)) AS turno,
                SUM(QUANTIDADE)     AS total_kg,
                COUNT(*)            AS registros
            FROM dbo.V_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {fil_sql}
              {loc_sql}
              {rec_sql}
              {ori_sql}
              {incl_sql}
            GROUP BY LTRIM(RTRIM(TURNO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + loc_p + rec_p + ori_p + incl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {"turno": r[0], "total_kg": float(r[1]), "registros": int(r[2])}
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
        TES 010 está bloqueada — não será incluída mesmo se solicitada.
        PENDENTE: tratar sinal de QUANTIDADE para TES 999 (saída com valor negativo).
        """
        fil_sql, fil_p = _filial_clause(filial)
        tes_sql, tes_p = _tes_clause(tes)
        ori_sql, ori_p = _origem_clause(origem)

        query = f"""
            SELECT TOP {limite}
                EMISSAO,
                LTRIM(RTRIM(TES))       AS tes,
                LTRIM(RTRIM(PRODUTO))   AS produto,
                LTRIM(RTRIM(DESCRICAO)) AS descricao,
                QUANTIDADE,
                LTRIM(RTRIM(LOTE))      AS lote,
                LTRIM(RTRIM(USUARIO))   AS usuario
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
            return [
                {
                    "emissao": str(r[0]),
                    "tes": r[1],
                    "tes_descricao": TES_MAP.get((r[1] or "").strip(), r[1]),
                    "produto": r[2],
                    "descricao": r[3],
                    "quantidade": float(r[4]) if r[4] is not None else 0.0,
                    "lote": r[5],
                    "usuario": r[6],
                    "parsed_produto": parse_produto(r[2]),
                }
                for r in cur.fetchall()
            ]

    # ── Consulta por lote ─────────────────────────────────────────────────────
    def get_por_lote(
        self,
        lote: str,
        filial: str | None = None,
    ) -> list[dict]:
        """
        Retorna todos os registros de um lote específico.
        Inclui turno e recurso para rastreabilidade completa da bobina.
        """
        fil_sql, fil_p = _filial_clause(filial)

        query = f"""
            SELECT
                EMISSAO,
                LTRIM(RTRIM(TES))       AS tes,
                LTRIM(RTRIM(PRODUTO))   AS produto,
                LTRIM(RTRIM(DESCRICAO)) AS descricao,
                QUANTIDADE,
                LTRIM(RTRIM(LOTE))      AS lote,
                LTRIM(RTRIM(USUARIO))   AS usuario,
                LTRIM(RTRIM(TURNO))     AS turno,
                LTRIM(RTRIM(RECURSO))   AS recurso
            FROM dbo.V_KARDEX
            WHERE LTRIM(RTRIM(LOTE)) = ?
              {fil_sql}
            ORDER BY EMISSAO DESC
        """
        params = [lote.strip()] + fil_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "emissao": str(r[0]),
                    "tes": r[1],
                    "tes_descricao": TES_MAP.get((r[1] or "").strip(), r[1]),
                    "produto": r[2],
                    "descricao": r[3],
                    "quantidade": float(r[4]) if r[4] is not None else 0.0,
                    "lote": r[5],
                    "usuario": r[6],
                    "turno": r[7],
                    "recurso": r[8],
                    "recurso_label": traduzir_recurso(r[8]) if r[8] else None,
                    "parsed_produto": parse_produto(r[2]),
                }
                for r in cur.fetchall()
            ]

    # ── Períodos disponíveis no banco ─────────────────────────────────────────
    def get_periodos_disponiveis(
        self,
        filial: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> list[dict]:
        """Retorna anos e meses com registros agrupados por ano."""
        fil_sql, fil_p = _filial_clause(filial)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)

        query = f"""
            SELECT YEAR(EMISSAO) AS ano, MONTH(EMISSAO) AS mes, COUNT(*) AS registros
            FROM dbo.V_KARDEX
            WHERE EMISSAO IS NOT NULL
              {fil_sql}
              {incl_sql}
            GROUP BY YEAR(EMISSAO), MONTH(EMISSAO)
            ORDER BY ano, mes
        """
        params = fil_p + incl_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            anos: dict[int, list[int]] = {}
            for r in cur.fetchall():
                ano, mes = int(r[0]), int(r[1])
                anos.setdefault(ano, []).append(mes)
            return [{"ano": ano, "meses": meses} for ano, meses in sorted(anos.items())]
