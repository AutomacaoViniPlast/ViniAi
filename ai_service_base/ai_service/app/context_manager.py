"""
context_manager.py — Gerenciamento do histórico de conversa.

Lê as últimas mensagens de uma sessão diretamente da tabela `mensagens`
no banco N8N, montando o contexto para a próxima resposta da IA.

Responsabilidade de escrita:
  O frontend salva cada mensagem (user e assistant) via backend Node.js.
  Este módulo é somente leitura — não duplica gravações.

Uso:
  ctx = PostgresContextManager()
  historico = ctx.get_recent(session_id="uuid-da-conversa", limit=6)
  # retorna list[ConversationTurn] em ordem cronológica
"""
from __future__ import annotations

from app.db import get_n8n_conn
from app.schemas import ConversationTurn


class PostgresContextManager:
    """Lê o histórico de conversa do banco N8N para compor o contexto da IA."""

    def get_recent(self, session_id: str, limit: int = 6) -> list[ConversationTurn]:
        """
        Retorna as últimas `limit` mensagens da conversa em ordem cronológica.

        Parâmetros:
          session_id : UUID da conversa (enviado pelo frontend no payload)
          limit      : número máximo de mensagens a retornar (padrão: 6)

        Retorna lista vazia se o banco N8N estiver inacessível (falha silenciosa).
        """
        try:
            with get_n8n_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT role, conteudo
                    FROM (
                        SELECT role, conteudo, criado_em
                        FROM mensagens
                        WHERE conversa_id = %s
                        ORDER BY criado_em DESC
                        LIMIT %s
                    ) sub
                    ORDER BY criado_em ASC
                    """,
                    (session_id, limit),
                ).fetchall()

            return [ConversationTurn(role=row[0], content=row[1]) for row in rows]

        except Exception as exc:
            print(f"[ContextManager] Erro ao buscar histórico da sessão {session_id}: {exc}")
            return []

    # ── Stubs de escrita (compatibilidade com o orchestrator) ─────────────────
    # A gravação é feita pelo backend Node.js — estes métodos existem apenas
    # para evitar erros caso o orchestrator os chame.

    def append_user_message(self, session_id: str, content: str) -> None:
        pass

    def append_assistant_message(self, session_id: str, content: str) -> None:
        pass
