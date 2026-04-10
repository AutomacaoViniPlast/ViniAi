"""
db.py — Pools de conexão com o PostgreSQL.

Gerencia dois pools de conexão independentes:

  _pool      → banco METABASE (dados de produção — view v_kardex_ld)
  _n8n_pool  → banco N8N (histórico de conversas — tabela mensagens)

O pool N8N é inicializado de forma tolerante a falhas: se o banco estiver
indisponível no startup, a API sobe normalmente e o histórico de conversa
simplesmente retorna vazio até a conexão ser restabelecida.

Uso:
  from app.db import get_conn, get_n8n_conn

  with get_conn() as conn:
      rows = conn.execute("SELECT ...").fetchall()
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote_plus

import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

# Carrega variáveis do .env (localizado um nível acima de /app)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Pool principal — METABASE (dados de produção) ─────────────────────────────
_DB_URL = (
    f"postgresql://{os.environ['DB_USER']}:{quote_plus(os.environ['DB_PASSWORD'])}"
    f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
)
_pool = ConnectionPool(_DB_URL, min_size=1, max_size=10, open=True)

# ── Pool secundário — N8N (histórico de conversas) ────────────────────────────
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


# ── Context managers ──────────────────────────────────────────────────────────

@contextmanager
def get_conn():
    """Fornece uma conexão do pool METABASE. Devolvida automaticamente ao sair do bloco."""
    with _pool.connection() as conn:
        yield conn


@contextmanager
def get_n8n_conn():
    """Fornece uma conexão do pool N8N (mensagens/conversas)."""
    if _n8n_pool is None:
        raise RuntimeError("Pool N8N não disponível — verifique as variáveis N8N_DB_* no .env")
    with _n8n_pool.connection() as conn:
        yield conn
