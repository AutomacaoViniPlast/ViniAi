"""
sql_service_sh6.py — Queries SQL para dbo.STG_PROD_SH6_VPLONAS.

Tabela exclusiva de apontamentos de produção das extrusoras (MACs).
Não misturar com STG_KARDEX — cada tabela tem propósito e escopo distintos.

Regras de cálculo (negócio):
  Produção mensal   → SUM(PESO_FILME_PASSADA) filtrado por DATA_APONT
  Produção diária   → SUM(PESO_FILME_PASSADA) filtrado por DATA_INI
  Metros/min        → SUM(QTDPROD2) / SUM(MINUTOS)   [divisão por zero protegida]
  KGH               → AVG(KGH) agrupado por recurso
  Filial padrão     → 010101 (VINIPLAST); 010201 = Confecção (futuro)
  Recurso padrão    → ('0003', '0007') — exclui REVISA automaticamente
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.db import get_mssql_conn


# ── Mapeamentos de negócio ─────────────────────────────────────────────────────

FILIAL_MAP: dict[str, str] = {
    "010101": "VINIPLAST",
    "010201": "Confecção",
}

RECURSO_MAP: dict[str, str] = {
    "0003": "Extrusora 1 (MAC1)",
    "0007": "Extrusora 2 (MAC2)",
    "0005": "Revisão",
    "0006": "Revisão 2",
}

# Recursos produtivos padrão — exclui REVISA
RECURSOS_PRODUCAO: tuple[str, ...] = ("0003", "0007")

RECURSOS_REVISAO: tuple[str, ...] = ("0005", "0006")

FILIAL_PADRAO = "010101"


# ── Helpers de tradução ────────────────────────────────────────────────────────

def traduzir_filial(codigo: str) -> str:
    return FILIAL_MAP.get(codigo.strip(), codigo)


def traduzir_recurso(codigo: str) -> str:
    return RECURSO_MAP.get(codigo.strip(), codigo)


def extrair_tipo_produto(produto: str) -> str:
    """Retorna os 3 primeiros caracteres do código do produto (ex: 'CLI', 'SUF')."""
    return produto.strip()[:3].upper() if produto else ""


# ── Helpers de cláusula SQL ────────────────────────────────────────────────────

def _parse_date(date_str: str):
    return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()


def _recursos_clause(recursos: list[str] | None) -> tuple[str, list]:
    """Filtra por lista de recursos; padrão são as duas extrusoras."""
    r = recursos or list(RECURSOS_PRODUCAO)
    ph = ", ".join(["?"] * len(r))
    return f"AND LTRIM(RTRIM(RECURSO)) IN ({ph})", r


def _filial_clause(filial: str | None) -> tuple[str, list]:
    f = filial or FILIAL_PADRAO
    return "AND LTRIM(RTRIM(FILIAL)) = ?", [f]


# ── Service ────────────────────────────────────────────────────────────────────

class SQLServiceSH6:
    """Consultas à tabela dbo.STG_PROD_SH6_VPLONAS."""

    # ── Produção total (mensal ou diária) ─────────────────────────────────────
    def get_producao_total(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        is_diaria: bool = False,
    ) -> Decimal:
        """
        Soma PESO_FILME_PASSADA no período.
        Mensal → DATA_APONT. Diária → DATA_INI.
        """
        col_data = "DATA_INI" if is_diaria else "DATA_APONT"
        rec_sql, rec_p = _recursos_clause(recursos)
        fil_sql, fil_p = _filial_clause(filial)
        query = f"""
            SELECT COALESCE(SUM(PESO_FILME_PASSADA), 0)
            FROM dbo.STG_PROD_SH6_VPLONAS
            WHERE {col_data} BETWEEN ? AND ?
              {fil_sql}
              {rec_sql}
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + rec_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Produção total por operador ───────────────────────────────────────────
    def get_producao_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        is_diaria: bool = False,
    ) -> Decimal:
        """Aceita nome completo ou login — usa LIKE para cobrir ambos."""
        col_data = "DATA_INI" if is_diaria else "DATA_APONT"
        rec_sql, rec_p = _recursos_clause(recursos)
        fil_sql, fil_p = _filial_clause(filial)
        query = f"""
            SELECT COALESCE(SUM(PESO_FILME_PASSADA), 0)
            FROM dbo.STG_PROD_SH6_VPLONAS
            WHERE {col_data} BETWEEN ? AND ?
              AND LOWER(LTRIM(RTRIM(NOME_USUARIO))) LIKE LOWER(?)
              {fil_sql}
              {rec_sql}
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim), f"%{operador.strip()}%"] + fil_p + rec_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            return Decimal(str(row[0])) if row and row[0] is not None else Decimal("0")

    # ── Ranking de produção por operador ──────────────────────────────────────
    def get_ranking_producao(
        self,
        data_inicio: str,
        data_fim: str,
        limite: int = 5,
        filial: str | None = None,
        recursos: list[str] | None = None,
        is_diaria: bool = False,
    ) -> list[dict]:
        col_data = "DATA_INI" if is_diaria else "DATA_APONT"
        rec_sql, rec_p = _recursos_clause(recursos)
        fil_sql, fil_p = _filial_clause(filial)
        query = f"""
            SELECT TOP {limite}
                LTRIM(RTRIM(NOME_USUARIO)) AS operador,
                SUM(PESO_FILME_PASSADA)    AS total_kg
            FROM dbo.STG_PROD_SH6_VPLONAS
            WHERE {col_data} BETWEEN ? AND ?
              {fil_sql}
              {rec_sql}
            GROUP BY LTRIM(RTRIM(NOME_USUARIO))
            ORDER BY total_kg DESC
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + rec_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {"posicao": i + 1, "operador": r[0], "total_kg": float(r[1])}
                for i, r in enumerate(cur.fetchall())
            ]

    # ── Metros por minuto ─────────────────────────────────────────────────────
    def get_metros_por_minuto(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        is_diaria: bool = False,
    ) -> dict:
        """
        SUM(QTDPROD2) / SUM(MINUTOS).
        Retorna metros, minutos e resultado calculado.
        """
        col_data = "DATA_INI" if is_diaria else "DATA_APONT"
        rec_sql, rec_p = _recursos_clause(recursos)
        fil_sql, fil_p = _filial_clause(filial)
        query = f"""
            SELECT
                COALESCE(SUM(QTDPROD2), 0) AS total_metros,
                COALESCE(SUM(MINUTOS),  0) AS total_minutos
            FROM dbo.STG_PROD_SH6_VPLONAS
            WHERE {col_data} BETWEEN ? AND ?
              {fil_sql}
              {rec_sql}
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + rec_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            row = cur.fetchone()
            metros  = float(row[0]) if row and row[0] else 0.0
            minutos = float(row[1]) if row and row[1] else 0.0
            resultado = round(metros / minutos, 4) if minutos > 0 else 0.0
            return {"metros": metros, "minutos": minutos, "resultado": resultado}

    # ── KGH (KG por hora) por recurso ─────────────────────────────────────────
    def get_kgh(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        is_diaria: bool = False,
    ) -> list[dict]:
        """Média de KGH agrupada por recurso."""
        col_data = "DATA_INI" if is_diaria else "DATA_APONT"
        rec_sql, rec_p = _recursos_clause(recursos)
        fil_sql, fil_p = _filial_clause(filial)
        query = f"""
            SELECT
                LTRIM(RTRIM(RECURSO)) AS recurso,
                ROUND(AVG(KGH), 2)    AS media_kgh,
                COUNT(*)              AS registros
            FROM dbo.STG_PROD_SH6_VPLONAS
            WHERE {col_data} BETWEEN ? AND ?
              {fil_sql}
              {rec_sql}
              AND KGH IS NOT NULL AND KGH > 0
            GROUP BY LTRIM(RTRIM(RECURSO))
            ORDER BY recurso
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + rec_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "recurso":       r[0],
                    "recurso_label": traduzir_recurso(r[0]),
                    "media_kgh":     float(r[1]) if r[1] else 0.0,
                    "registros":     int(r[2]),
                }
                for r in cur.fetchall()
            ]

    # ── Produção agrupada por recurso (extrusora) ─────────────────────────────
    def get_producao_por_recurso(
        self,
        data_inicio: str,
        data_fim: str,
        filial: str | None = None,
        recursos: list[str] | None = None,
        is_diaria: bool = False,
    ) -> list[dict]:
        col_data = "DATA_INI" if is_diaria else "DATA_APONT"
        rec_sql, rec_p = _recursos_clause(recursos)
        fil_sql, fil_p = _filial_clause(filial)
        query = f"""
            SELECT
                LTRIM(RTRIM(RECURSO))   AS recurso,
                SUM(PESO_FILME_PASSADA) AS total_kg,
                COUNT(*)                AS registros
            FROM dbo.STG_PROD_SH6_VPLONAS
            WHERE {col_data} BETWEEN ? AND ?
              {fil_sql}
              {rec_sql}
            GROUP BY LTRIM(RTRIM(RECURSO))
            ORDER BY recurso
        """
        params = [_parse_date(data_inicio), _parse_date(data_fim)] + fil_p + rec_p
        with get_mssql_conn() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            return [
                {
                    "recurso":       r[0],
                    "recurso_label": traduzir_recurso(r[0]),
                    "total_kg":      float(r[1]) if r[1] else 0.0,
                    "registros":     int(r[2]),
                }
                for r in cur.fetchall()
            ]
