from __future__ import annotations

from decimal import Decimal
from app.db import get_conn


# ── Helpers de cláusula SQL ───────────────────────────────────────────────────

def _origem_clause(origem: str | None) -> tuple[str, list]:
    """Filtro opcional por tipo de movimentação. Registros NULL não são excluídos."""
    if origem:
        return "AND TRIM(origem) = %s", [origem]
    return "", []


def _incluir_clause(incluir: list[str] | None) -> tuple[str, list]:
    """Filtra apenas os operadores informados (ex: somente revisão)."""
    if incluir:
        ph = ", ".join(["%s"] * len(incluir))
        return f"AND TRIM(usuario) IN ({ph})", list(incluir)
    return "", []


def _excluir_clause(excluir: list[str] | None) -> tuple[str, list]:
    """Exclui operadores do resultado (ex: expedição em rankings de produção)."""
    if excluir:
        ph = ", ".join(["%s"] * len(excluir))
        return f"AND TRIM(usuario) NOT IN ({ph})", list(excluir)
    return "", []


class SQLService:

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
            SELECT COALESCE(SUM(total), 0)
            FROM v_kardex_ld
            WHERE TRIM(usuario) ILIKE %s
              AND TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              {orig_sql}
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, [f"%{operador.strip()}%", data_inicio, data_fim] + orig_p)
                row = cur.fetchone()
                return row[0] if row else Decimal("0")

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
            SELECT COALESCE(SUM(total), 0)
            FROM v_kardex_ld
            WHERE TRIM(usuario) ILIKE %s
              AND TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              AND SUBSTRING(TRIM(produto), 5, 1) = 'Y'
              {orig_sql}
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, [f"%{operador.strip()}%", data_inicio, data_fim] + orig_p)
                row = cur.fetchone()
                return row[0] if row else Decimal("0")

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
        orig_sql,  orig_p  = _origem_clause(origem)
        incl_sql,  incl_p  = _incluir_clause(filtro_usuarios)
        excl_sql,  excl_p  = _excluir_clause(excluir_usuarios)
        query = f"""
            SELECT TRIM(usuario) AS operador, SUM(total) AS total_kg
            FROM v_kardex_ld
            WHERE TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              AND SUBSTRING(TRIM(produto), 5, 1) = 'Y'
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY TRIM(usuario)
            ORDER BY total_kg DESC
            LIMIT %s
        """
        params = [data_inicio, data_fim] + incl_p + excl_p + orig_p + [limite]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return [
                    {"posicao": i + 1, "operador": r[0], "total_kg": float(r[1])}
                    for i, r in enumerate(cur.fetchall())
                ]

    # ── Ranking produtos por LD ───────────────────────────────────────────────
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
            SELECT
                TRIM(produto)  AS produto,
                SUM(total)     AS total_kg,
                COUNT(*)       AS ocorrencias
            FROM v_kardex_ld
            WHERE TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              AND SUBSTRING(TRIM(produto), 5, 1) = 'Y'
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY TRIM(produto)
            ORDER BY total_kg DESC
            LIMIT %s
        """
        params = [data_inicio, data_fim] + incl_p + excl_p + orig_p + [limite]
        with get_conn() as conn:
            with conn.cursor() as cur:
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
            SELECT COALESCE(SUM(total), 0)
            FROM v_kardex_ld
            WHERE TRIM(produto) ILIKE %s
              AND TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              {orig_sql}
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, [f"%{produto.strip()}%", data_inicio, data_fim] + orig_p)
                row = cur.fetchone()
                return row[0] if row else Decimal("0")

    # ── Ranking geral de produção (com exclusão de expedição) ─────────────────
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
            SELECT TRIM(usuario) AS operador, SUM(total) AS total_kg
            FROM v_kardex_ld
            WHERE TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY TRIM(usuario)
            ORDER BY total_kg DESC
            LIMIT %s
        """
        params = [data_inicio, data_fim] + incl_p + excl_p + orig_p + [limite]
        with get_conn() as conn:
            with conn.cursor() as cur:
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
            SELECT TRIM(turno) AS turno, SUM(total) AS total_kg, COUNT(*) AS registros
            FROM v_kardex_ld
            WHERE TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              {incl_sql}
              {excl_sql}
              {orig_sql}
            GROUP BY TRIM(turno)
            ORDER BY total_kg DESC
        """
        params = [data_inicio, data_fim] + incl_p + excl_p + orig_p
        with get_conn() as conn:
            with conn.cursor() as cur:
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
            SELECT COALESCE(SUM(total), 0)
            FROM v_kardex_ld
            WHERE TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              {incl_sql}
              {orig_sql}
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, [data_inicio, data_fim] + incl_p + orig_p)
                row = cur.fetchone()
                return row[0] if row else Decimal("0")

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
            SELECT COALESCE(SUM(total), 0)
            FROM v_kardex_ld
            WHERE TO_DATE(emissao, 'DD/MM/YYYY')
                  BETWEEN TO_DATE(%s, 'DD/MM/YYYY') AND TO_DATE(%s, 'DD/MM/YYYY')
              AND SUBSTRING(TRIM(produto), 5, 1) = 'Y'
              {incl_sql}
              {orig_sql}
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, [data_inicio, data_fim] + incl_p + orig_p)
                row = cur.fetchone()
                return row[0] if row else Decimal("0")

    # ── Períodos disponíveis no banco ─────────────────────────────────────────
    def get_periodos_disponiveis(
        self,
        filtro_usuarios: list[str] | None = None,
    ) -> list[dict]:
        """Retorna anos e meses com registros, agrupados por ano."""
        incl_sql, incl_p = _incluir_clause(filtro_usuarios)
        query = f"""
            SELECT
                EXTRACT(YEAR  FROM TO_DATE(emissao, 'DD/MM/YYYY'))::int AS ano,
                EXTRACT(MONTH FROM TO_DATE(emissao, 'DD/MM/YYYY'))::int AS mes,
                COUNT(*) AS registros
            FROM v_kardex_ld
            WHERE emissao IS NOT NULL
              {incl_sql}
            GROUP BY ano, mes
            ORDER BY ano, mes
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, incl_p)
                rows = cur.fetchall()
                # Agrupa por ano
                anos: dict[int, list[int]] = {}
                for r in rows:
                    ano, mes = int(r[0]), int(r[1])
                    anos.setdefault(ano, []).append(mes)
                return [{"ano": ano, "meses": meses} for ano, meses in sorted(anos.items())]

    # ── Operadores de um setor presentes no banco ─────────────────────────────
    def get_review_operators(self, operadores: list[str]) -> list[str]:
        if not operadores:
            return []
        ph = ", ".join(["%s"] * len(operadores))
        query = f"""
            SELECT DISTINCT TRIM(usuario)
            FROM v_kardex_ld
            WHERE TRIM(usuario) IN ({ph})
            ORDER BY 1
        """
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, operadores)
                return [r[0] for r in cur.fetchall() if r[0]]
