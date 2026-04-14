"""
sql_service.py — Queries SQL executadas contra o SQL Server (METABASE).

Centraliza todas as consultas aos dados industriais. Nenhuma lógica de negócio
ou formatação de resposta deve existir aqui — apenas execução de SQL e
retorno de dados brutos.

Tabela principal: dbo.STG_KARDEX
Colunas relevantes:
  USUARIO   → operador (varchar 25, com espaços) — sempre usar LTRIM(RTRIM())
  EMISSAO   → data nativa (date) — comparar diretamente com BETWEEN ? AND ?
  PRODUTO   → código do produto (varchar 15)
  QUALIDADE → indicador de qualidade: 'Y'=LD (defeito), 'I'=Inteiro
  TOTAL     → peso em KG (float)
  TURNO     → turno de produção (varchar 5)
  ORIGEM    → tipo de movimentação: SD1 (Entrada), SD2 (Saída), SD3 (Interna)
              Atenção: muitos registros têm origem NULL — não forçar filtro

Regras de query (SQL Server)
─────────────────────────────
  - Sempre usar LTRIM(RTRIM(USUARIO)) para remover espaços
  - Parâmetros com ? (pyodbc), NÃO %s
  - Case-insensitive: LOWER(col) LIKE LOWER(?)
  - Paginação: TOP N (não LIMIT)
  - Filtro por origem é OPCIONAL
  - LD = QUALIDADE = 'Y'
  - EMISSAO já é tipo date — sem conversão de texto

Datas recebidas como string 'DD/MM/YYYY' são convertidas para datetime.date
internamente antes de passarem ao pyodbc.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from app.db import get_mssql_conn


# ── Conversão de datas ────────────────────────────────────────────────────────

def _parse_date(date_str: str):
    """Converte string DD/MM/YYYY em datetime.date para o pyodbc."""
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()


# ── Helpers de cláusula SQL ───────────────────────────────────────────────────

def _origem_clause(origem: str | None) -> tuple[str, list]:
    """Filtro opcional por tipo de movimentação."""
    if origem:
        return "AND LTRIM(RTRIM(ORIGEM)) = ?", [origem]
    return "", []


def _incluir_clause(incluir: list[str] | None) -> tuple[str, list]:
    """Inclui apenas os operadores informados."""
    if incluir:
        ph = ", ".join(["?"] * len(incluir))
        return f"AND LTRIM(RTRIM(USUARIO)) IN ({ph})", list(incluir)
    return "", []


def _excluir_clause(excluir: list[str] | None) -> tuple[str, list]:
    """Exclui operadores do resultado."""
    if excluir:
        ph = ", ".join(["?"] * len(excluir))
        return f"AND LTRIM(RTRIM(USUARIO)) NOT IN ({ph})", list(excluir)
    return "", []


# ── Service ───────────────────────────────────────────────────────────────────

class SQLService:
    """Executa consultas SQL Server e retorna dados brutos para o orchestrator."""

    # ── Produção total por operador ───────────────────────────────────────────
    def get_producao_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
        origem: str | None = None,
    ) -> Decimal:
        orig_sql, orig_p = _origem_clause(origem)
        query = f"""
            SELECT COALESCE(SUM(TOTAL), 0)
            FROM dbo.STG_KARDEX
            WHERE LOWER(LTRIM(RTRIM(USUARIO))) LIKE LOWER(?)
              AND EMISSAO BETWEEN ? AND ?
              {orig_sql}
        """
        params = [f"%{operador.strip()}%", _parse_date(data_inicio), _parse_date(data_fim)] + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Geração de LD por operador ────────────────────────────────────────────
    def get_ld_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
        origem: str | None = None,
    ) -> Decimal:
        orig_sql, orig_p = _origem_clause(origem)
        query = f"""
            SELECT COALESCE(SUM(TOTAL), 0)
            FROM dbo.STG_KARDEX
            WHERE LOWER(LTRIM(RTRIM(USUARIO))) LIKE LOWER(?)
              AND EMISSAO BETWEEN ? AND ?
              AND QUALIDADE = 'Y'
              {orig_sql}
        """
        params = [f"%{operador.strip()}%", _parse_date(data_inicio), _parse_date(data_fim)] + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Ranking de revisão por LD ─────────────────────────────────────────────
    def get_ranking_usuarios_ld(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
        excluir_usuarios: list[str] | None = None,
    ) -> list[dict]:
        orig_sql, orig_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        excl_sql, excl_p = _excluir_clause(excluir_usuarios)
        query = f"""
            SELECT TOP {limite} LTRIM(RTRIM(USUARIO)) AS operador, SUM(TOTAL) AS total_kg
            FROM dbo.STG_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND QUALIDADE = 'Y'
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY LTRIM(RTRIM(USUARIO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + incl_p + excl_p + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {"posicao": i + 1, "operador": r[0], "total_kg": float(r[1])}
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Ranking de produtos por LD ────────────────────────────────────────────
    def get_ranking_produtos_ld(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
        excluir_usuarios: list[str] | None = None,
    ) -> list[dict]:
        orig_sql, orig_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        excl_sql, excl_p = _excluir_clause(excluir_usuarios)
        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(PRODUTO)) AS produto,
                SUM(TOTAL)            AS total_kg,
                COUNT(*)              AS ocorrencias
            FROM dbo.STG_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND QUALIDADE = 'Y'
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY LTRIM(RTRIM(PRODUTO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + incl_p + excl_p + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "posicao": i + 1,
                    "produto": r[0],
                    "total_kg": float(r[1]),
                    "ocorrencias": int(r[2]),
                }
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Produção por produto específico ──────────────────────────────────────
    def get_producao_por_produto(
        self,
        produto: str,
        data_inicio: str,
        data_fim: str,
        origem: str | None = None,
    ) -> Decimal:
        orig_sql, orig_p = _origem_clause(origem)
        query = f"""
            SELECT COALESCE(SUM(TOTAL), 0)
            FROM dbo.STG_KARDEX
            WHERE LOWER(LTRIM(RTRIM(PRODUTO))) LIKE LOWER(?)
              AND EMISSAO BETWEEN ? AND ?
              {orig_sql}
        """
        params = [f"%{produto.strip()}%", _parse_date(data_inicio), _parse_date(data_fim)] + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Ranking geral de produção ─────────────────────────────────────────────
    def get_ranking_producao_geral(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
        excluir_usuarios: list[str] | None = None,
    ) -> list[dict]:
        orig_sql, orig_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        excl_sql, excl_p = _excluir_clause(excluir_usuarios)
        query = f"""
            SELECT TOP {limite} LTRIM(RTRIM(USUARIO)) AS operador, SUM(TOTAL) AS total_kg
            FROM dbo.STG_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY LTRIM(RTRIM(USUARIO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + incl_p + excl_p + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {"posicao": i + 1, "operador": r[0], "total_kg": float(r[1])}
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Produção por turno ────────────────────────────────────────────────────
    def get_producao_por_turno(
        self,
        data_inicio: str,
        data_fim: str,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
        excluir_usuarios: list[str] | None = None,
    ) -> list[dict]:
        orig_sql, orig_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        excl_sql, excl_p = _excluir_clause(excluir_usuarios)
        query = f"""
            SELECT LTRIM(RTRIM(TURNO)) AS turno, SUM(TOTAL) AS total_kg, COUNT(*) AS registros
            FROM dbo.STG_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY LTRIM(RTRIM(TURNO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + incl_p + excl_p + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {"turno": r[0], "total_kg": float(r[1]), "registros": int(r[2])}
                for r in cur.fetchall()
            ]

    # ── Total geral da fábrica ────────────────────────────────────────────────
    def get_total_fabrica(
        self,
        data_inicio: str,
        data_fim: str,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> Decimal:
        orig_sql, orig_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        query = f"""
            SELECT COALESCE(SUM(TOTAL), 0)
            FROM dbo.STG_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              {incl_sql}
              {orig_sql}
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + incl_p + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Total de LD da fábrica ────────────────────────────────────────────────
    def get_total_ld_fabrica(
        self,
        data_inicio: str,
        data_fim: str,
        origem: str | None = None,
        filtro_usuarios: list[str] | None = None,
    ) -> Decimal:
        orig_sql, orig_p = _origem_clause(origem)
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        query = f"""
            SELECT COALESCE(SUM(TOTAL), 0)
            FROM dbo.STG_KARDEX
            WHERE EMISSAO BETWEEN ? AND ?
              AND QUALIDADE = 'Y'
              {incl_sql}
              {orig_sql}
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + incl_p + orig_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Períodos disponíveis no banco ─────────────────────────────────────────
    def get_periodos_disponiveis(
        self,
        filtro_usuarios: list[str] | None = None,
    ) -> list[dict]:
        """Retorna anos e meses com registros, agrupados por ano."""
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        query = f"""
            SELECT YEAR(EMISSAO) AS ano, MONTH(EMISSAO) AS mes, COUNT(*) AS registros
            FROM dbo.STG_KARDEX
            WHERE EMISSAO IS NOT NULL
              {incl_sql}
            GROUP BY YEAR(EMISSAO), MONTH(EMISSAO)
            ORDER BY ano, mes
        """
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, incl_p)
            rows = cur.fetchall()
            anos: dict[int, list[int]] = {}
            for r in rows:
                ano, mes = int(r[0]), int(r[1])
                anos.setdefault(ano, []).append(mes)
            return [{"ano": ano, "meses": meses} for ano, meses in sorted(anos.items())]

    # ── Operadores de um setor presentes no banco ─────────────────────────────
    def get_review_operators(self, operadores: list[str]) -> list[str]:
        """Verifica quais operadores da lista têm registros na tabela."""
        if not operadores:
            return []
        ph = ", ".join(["?"] * len(operadores))
        query = f"""
            SELECT DISTINCT LTRIM(RTRIM(USUARIO))
            FROM dbo.STG_KARDEX
            WHERE LTRIM(RTRIM(USUARIO)) IN ({ph})
            ORDER BY 1
        """
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, operadores)
            return [r[0] for r in cur.fetchall() if r[0]]
