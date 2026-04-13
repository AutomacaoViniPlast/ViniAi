from __future__ import annotations

from app.db import get_n8n_conn
from app.schemas import ConversationTurn


class PostgresContextManager:
    """
    Lê o histórico de conversa diretamente da tabela `mensagens` no banco N8N.

    O frontend já é responsável por salvar cada mensagem (user e assistant)
    via o backend Node.js. O AI service apenas lê o histórico para montar
    o contexto da próxima resposta — sem escrita duplicada.
    """

    def get_recent(self, session_id: str, limit: int = 6) -> list[ConversationTurn]:
        """
        Retorna as últimas `limit` mensagens da conversa, em ordem cronológica.
        session_id = conversa_id (UUID) enviado pelo frontend.
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
            # Se o banco N8N não estiver acessível, retorna vazio sem travar
            print(f"[ContextManager] Erro ao buscar histórico: {exc}")
            return []

    # ── Métodos mantidos por compatibilidade com o orchestrator ──────────────
    # O frontend salva as mensagens — o AI service não precisa gravar nada.

    def append_user_message(self, session_id: str, content: str) -> None:
        pass

    def append_assistant_message(self, session_id: str, content: str) -> None:
        pass
