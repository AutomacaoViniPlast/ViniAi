"""
sql_service_apont_rev.py — Queries SQL para dbo.STG_APONT_REV_GERAL.

Tabela de apontamentos de revisão — registros individuais de inspeção de bobinas.
Cada linha = uma bobina revisada por um operador da revisão.

Colunas principais usadas aqui:
  OPER_BOB   → login do operador de revisão (ex: kaua.chagas)
  QTDPROD    → quantidade de bobinas revisadas
  QTDPROD2   → peso revisado em KG
  DATAAPONT  → data/hora do apontamento (datetimeoffset -03:00)
  MOTPERDA   → código do motivo de perda (MSP008 = BAG/descarte)
  DESCPERDA  → descrição da perda

Regras SQL (SQL Server — pyodbc):
  - Parâmetros com ? (nunca %s)
  - LTRIM(RTRIM()) para remover espaços nas colunas texto
  - CAST(DATAAPONT AS DATE) para filtrar por data sem a hora
  - CONVERT(date, ?, 103) para converter DD/MM/YYYY em date
  - TOP N para paginação (nunca LIMIT)
"""
from __future__ import annotations

from decimal import Decimal

from app.db import get_mssql_conn


class SQLServiceApontRev:
    """Consultas à tabela STG_APONT_REV_GERAL."""

    def get_ranking_revisao(
        self,
        data_inicio: str,
        data_fim: str,
        top_n: int = 5,
    ) -> list[dict]:
        """
        Retorna os operadores com mais KG revisados no período.

        Parâmetros:
          data_inicio : DD/MM/YYYY (inclusive)
          data_fim    : DD/MM/YYYY (inclusive)
          top_n       : limite de resultados (padrão: 5)

        Retorna lista de dicts com: operador, total_kg, registros, posicao
        """
        sql = f"""
            SELECT TOP {top_n}
                LTRIM(RTRIM(OPER_BOB))  AS operador,
                SUM(QTDPROD2)           AS total_kg,
                COUNT(*)                AS registros
            FROM dbo.STG_APONT_REV_GERAL
            WHERE CAST(DATAAPONT AS DATE)
                  BETWEEN CONVERT(date, ?, 103) AND CONVERT(date, ?, 103)
              AND LTRIM(RTRIM(OPER_BOB)) != ''
            GROUP BY LTRIM(RTRIM(OPER_BOB))
            ORDER BY total_kg DESC
        """
        with get_mssql_conn() as conn:
            rows = conn.execute(sql, (data_inicio, data_fim)).fetchall()

        result = []
        for pos, row in enumerate(rows, start=1):
            result.append({
                "posicao":   pos,
                "operador":  row[0] or "",
                "total_kg":  float(row[1] or 0),
                "registros": int(row[2] or 0),
            })
        return result

    def get_revisao_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
    ) -> dict:
        """
        Retorna total revisado por um operador específico no período.

        Retorna dict com: total_kg, total_bobinas
        """
        sql = """
            SELECT
                SUM(QTDPROD2) AS total_kg,
                COUNT(*)      AS total_bobinas
            FROM dbo.STG_APONT_REV_GERAL
            WHERE CAST(DATAAPONT AS DATE)
                  BETWEEN CONVERT(date, ?, 103) AND CONVERT(date, ?, 103)
              AND LOWER(LTRIM(RTRIM(OPER_BOB))) = LOWER(?)
        """
        with get_mssql_conn() as conn:
            row = conn.execute(sql, (data_inicio, data_fim, operador)).fetchone()

        return {
            "total_kg":      float(row[0] or 0) if row else 0.0,
            "total_bobinas": int(row[1] or 0) if row else 0,
        }
