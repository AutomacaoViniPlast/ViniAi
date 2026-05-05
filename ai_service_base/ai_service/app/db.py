"""
db.py — Conexões com os bancos de dados do ViniAI.

Dois bancos distintos:

  SQL Server (METABASE) → dados industriais: produção, kardex, PCP
    Tabelas: dbo.STG_KARDEX, dbo.STG_PROD_SH6_VPLONAS, dbo.STG_PROD_SD3
    Conexão via pyodbc (ODBC Driver 17 for SQL Server)
    get_mssql_conn() → retorna conexão pyodbc

  PostgreSQL (N8N) → histórico de conversas (tabela mensagens)
    Conexão via psycopg-pool
    get_n8n_conn() → context manager com conexão do pool

Uso:
  from app.db import get_mssql_conn, get_n8n_conn

  with get_mssql_conn() as conn:
      cur = conn.cursor()
      cur.execute("SELECT ...")
      rows = cur.fetchall()

  with get_n8n_conn() as conn:
      rows = conn.execute("SELECT ...").fetchall()
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote_plus

import pyodbc
import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

# Carrega variáveis do .env (localizado um nível acima de /app)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ── SQL Server — dados industriais ────────────────────────────────────────────
_MSSQL_CONN_STR = (
    f"DRIVER={{{os.environ['MSSQL_DRIVER']}}};"
    f"SERVER={os.environ['MSSQL_HOST']},{os.environ['MSSQL_PORT']};"
    f"DATABASE={os.environ['MSSQL_DB']};"
    f"UID={os.environ['MSSQL_USER']};"
    f"PWD={os.environ['MSSQL_PASSWORD']}"
)


@contextmanager
def get_mssql_conn():
    """
    Fornece uma conexão pyodbc com o SQL Server (METABASE).
    Sempre abre e fecha uma nova conexão — pyodbc não tem pool nativo.
    Uso: with get_mssql_conn() as conn: ...
    """
    conn = pyodbc.connect(_MSSQL_CONN_STR, timeout=15)
    conn.timeout = 30  # timeout por query (SQL_ATTR_QUERY_TIMEOUT)
    try:
        yield conn
    finally:
        conn.close()


# ── PostgreSQL N8N — histórico de conversas ───────────────────────────────────
# Inicialização tolerante: falha aqui não impede o startup do FastAPI.
_n8n_pool: ConnectionPool | None = None
try:
    _N8N_DB_URL = (
        f"postgresql://{os.environ['N8N_DB_USER']}:{quote_plus(os.environ['N8N_DB_PASSWORD'])}"
        f"@{os.environ['N8N_DB_HOST']}:{os.environ['N8N_DB_PORT']}/{os.environ['N8N_DB_NAME']}"
    )
    _n8n_pool = ConnectionPool(_N8N_DB_URL, min_size=1, max_size=5, open=True)
except Exception as exc:
    print(f"[db] Pool N8N não inicializado — histórico de conversa desabilitado: {exc}")


@contextmanager
def get_n8n_conn():
    """Fornece uma conexão do pool PostgreSQL N8N (mensagens/conversas)."""
    if _n8n_pool is None:
        raise RuntimeError("Pool N8N não disponível — verifique as variáveis N8N_DB_* no .env")
    with _n8n_pool.connection() as conn:
        yield conn
