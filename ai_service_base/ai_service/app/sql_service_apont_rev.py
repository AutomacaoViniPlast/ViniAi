"""
sql_service_apont_rev.py — Queries SQL para V_APONT_REV_GERAL.

View de apontamentos de revisão — registros individuais de inspeção de bobinas.
Cada linha = uma bobina revisada por um operador da revisão.

Colunas principais usadas aqui:
  OPER_BOB   → login do operador de revisão (ex: kaua.chagas)
  PRODUTO    → código do produto; posição 5 define o tipo:
                 I = INTEIRO, P = FORA DE PADRÃO, Y = LD
  QTDPROD    → metros revisados (usado para INTEIRO e FORA DE PADRÃO)
  QTDPROD2   → metros revisados (usado para LD e demais tipos)
  DATAAPONT  → data/hora do apontamento (datetimeoffset -03:00)
  MOTPERDA   → motivo de perda (incluído no total — perdas fazem parte da revisão)

Fórmula de metros (replicada do Metabase):
  TIPO      = SUBSTRING(PRODUTO, 5, 1)
  CONDIÇÃO  = I→INTEIRO, P→FORA DE PADRÃO, Y→LD, MSP008→BAG
  METROS    = QTDPROD  se CONDIÇÃO IN (INTEIRO, FORA DE PADRÃO)
            = QTDPROD2 caso contrário

Regras SQL (SQL Server — pyodbc):
  - Parâmetros com ? (nunca %s)
  - LTRIM(RTRIM()) para remover espaços nas colunas texto
  - CAST(DATAAPONT AS DATE) para filtrar por data sem a hora
  - CONVERT(date, ?, 103) para converter DD/MM/YYYY em date
  - TOP N para paginação (nunca LIMIT)
"""
from __future__ import annotations

from app.db import get_mssql_conn

_METROS_CASE = """
    CASE
        WHEN SUBSTRING(LTRIM(RTRIM(PRODUTO)), 5, 1) IN ('I', 'P') THEN QTDPROD
        ELSE QTDPROD2
    END
""".strip()

# Para extrusora: metros sempre em QTDPROD (diferente da revisão que usa CASE por tipo)
_METROS_PRODUCAO = "COALESCE(QTDPROD, 0)"

class SQLServiceApontRev:
    """Consultas à view V_APONT_REV_GERAL."""

    def get_ranking_producao_extrusora(
        self,
        data_inicio: str,
        data_fim: str,
        top_n: int = 10,
        operadores: list[str] | None = None,
    ) -> list[dict]:
        """
        Retorna os operadores de extrusora com mais metros produzidos no período.
        Usa OPER_MP (operador de máquina/produção), diferente de OPER_BOB (revisão).
        """
        filtro_op = ""
        params: tuple = (data_inicio, data_fim)
        if operadores:
            placeholders = ", ".join("?" * len(operadores))
            filtro_op = f"AND LOWER(LTRIM(RTRIM(OPER_MP))) IN ({placeholders})"
            params = (data_inicio, data_fim, *[op.lower() for op in operadores])

        sql = f"""
            SELECT TOP {top_n}
                LTRIM(RTRIM(OPER_MP))        AS operador,
                SUM({_METROS_PRODUCAO})      AS total_metros,
                COUNT(*)                     AS registros
            FROM V_APONT_REV_GERAL
            WHERE CAST(DATAAPONT AS DATE)
                  BETWEEN CONVERT(date, ?, 103) AND CONVERT(date, ?, 103)
              AND LTRIM(RTRIM(OPER_MP)) != ''
              {filtro_op}
            GROUP BY LTRIM(RTRIM(OPER_MP))
            ORDER BY total_metros DESC
        """
        with get_mssql_conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            {
                "posicao":      pos,
                "operador":     row[0] or "",
                "total_metros": float(row[1] or 0),
                "registros":    int(row[2] or 0),
            }
            for pos, row in enumerate(rows, start=1)
        ]

    def get_ranking_revisao(
        self,
        data_inicio: str,
        data_fim: str,
        top_n: int = 5,
        operadores: list[str] | None = None,
    ) -> list[dict]:
        """
        Retorna os operadores com mais metros revisados no período.

        Parâmetros:
          data_inicio : DD/MM/YYYY (inclusive)
          data_fim    : DD/MM/YYYY (inclusive)
          top_n       : limite de resultados (padrão: 5)
          operadores  : lista de logins permitidos (filtra OPER_BOB)

        Retorna lista de dicts com: operador, total_metros, registros, posicao
        """
        filtro_op = ""
        params: tuple = (data_inicio, data_fim)
        if operadores:
            placeholders = ", ".join("?" * len(operadores))
            filtro_op = f"AND LOWER(LTRIM(RTRIM(OPER_BOB))) IN ({placeholders})"
            params = (data_inicio, data_fim, *[op.lower() for op in operadores])

        sql = f"""
            SELECT TOP {top_n}
                LTRIM(RTRIM(OPER_BOB))       AS operador,
                SUM({_METROS_CASE})          AS total_metros,
                COUNT(*)                     AS registros
            FROM V_APONT_REV_GERAL
            WHERE CAST(DATAAPONT AS DATE)
                  BETWEEN CONVERT(date, ?, 103) AND CONVERT(date, ?, 103)
              AND LTRIM(RTRIM(OPER_BOB)) != ''
              {filtro_op}
            GROUP BY LTRIM(RTRIM(OPER_BOB))
            ORDER BY total_metros DESC
        """
        with get_mssql_conn() as conn:
            rows = conn.execute(sql, params).fetchall()

        result = []
        for pos, row in enumerate(rows, start=1):
            result.append({
                "posicao":       pos,
                "operador":      row[0] or "",
                "total_metros":  float(row[1] or 0),
                "registros":     int(row[2] or 0),
            })
        return result

    def get_periodos_disponiveis(self) -> list[dict]:
        """
        Retorna anos e meses com dados em V_APONT_REV_GERAL, agrupados por ano.

        Retorna lista de dicts com: ano, meses (list[int])
        """
        sql = """
            SELECT
                YEAR(CAST(DATAAPONT AS DATE))  AS ano,
                MONTH(CAST(DATAAPONT AS DATE)) AS mes
            FROM V_APONT_REV_GERAL
            WHERE DATAAPONT IS NOT NULL
            GROUP BY
                YEAR(CAST(DATAAPONT AS DATE)),
                MONTH(CAST(DATAAPONT AS DATE))
            ORDER BY ano, mes
        """
        with get_mssql_conn() as conn:
            rows = conn.execute(sql).fetchall()

        anos: dict[int, list[int]] = {}
        for row in rows:
            ano, mes = int(row[0]), int(row[1])
            anos.setdefault(ano, []).append(mes)
        return [{"ano": ano, "meses": meses} for ano, meses in sorted(anos.items())]

    def get_revisao_por_operador(
        self,
        operador: str,
        data_inicio: str,
        data_fim: str,
    ) -> dict:
        """
        Retorna total revisado por um operador específico no período.

        Retorna dict com: total_metros, total_bobinas
        """
        sql = f"""
            SELECT
                SUM({_METROS_CASE}) AS total_metros,
                COUNT(*)            AS total_bobinas
            FROM V_APONT_REV_GERAL
            WHERE CAST(DATAAPONT AS DATE)
                  BETWEEN CONVERT(date, ?, 103) AND CONVERT(date, ?, 103)
              AND LOWER(LTRIM(RTRIM(OPER_BOB))) = LOWER(?)
        """
        with get_mssql_conn() as conn:
            row = conn.execute(sql, (data_inicio, data_fim, operador)).fetchone()

        return {
            "total_metros":  float(row[0] or 0) if row else 0.0,
            "total_bobinas": int(row[1] or 0) if row else 0,
        }
