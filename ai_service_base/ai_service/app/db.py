from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from urllib.parse import quote_plus

import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

# Carrega .env a partir da raiz do projeto (um nível acima de /app)
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_DB_URL = (
    f"postgresql://{os.environ['DB_USER']}:{quote_plus(os.environ['DB_PASSWORD'])}"
    f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
)

# Pool: mínimo 1, máximo 10 conexões abertas simultaneamente
_pool = ConnectionPool(_DB_URL, min_size=1, max_size=10, open=True)


@contextmanager
def get_conn():
    """Fornece uma conexão do pool; devolve automaticamente ao sair do bloco."""
    with _pool.connection() as conn:
        yield conn
