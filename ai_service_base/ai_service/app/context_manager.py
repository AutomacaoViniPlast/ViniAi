"""
context_manager.py — Gerenciamento do histórico de conversa.

Lê as últimas mensagens de uma sessão diretamente da tabela `mensagens`
no banco N8N, montando o contexto para a próxima resposta da IA.

Responsabilidade de escrita:
  Mensagens de conversa (user/assistant) são gravadas pelo backend Node.js.
  Este módulo não duplica essas gravações.
  Intents resolvidos (session_intents) são gravados aqui — cada consulta SQL
  bem-sucedida salva o InterpretationResult para carry-over preciso nas
  mensagens de acompanhamento.

Uso:
  ctx = PostgresContextManager()
  historico = ctx.get_recent(session_id="uuid-da-conversa", limit=6)
  # retorna list[ConversationTurn] em ordem cronológica
"""
from __future__ import annotations

import json

from app.db import get_n8n_conn
from app.schemas import ConversationTurn, InterpretationResult


class PostgresContextManager:
    """Lê o histórico de conversa do banco N8N e persiste intents resolvidos."""

    def __init__(self) -> None:
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Cria a tabela session_intents se ainda não existir (idempotente)."""
        try:
            with get_n8n_conn() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_intents (
                        id           SERIAL PRIMARY KEY,
                        session_id   TEXT NOT NULL,
                        created_at   TIMESTAMPTZ DEFAULT NOW(),
                        intent       TEXT NOT NULL,
                        route        TEXT NOT NULL,
                        metric       TEXT,
                        entity_type  TEXT,
                        entity_value TEXT,
                        data_inicio  TEXT,
                        data_fim     TEXT,
                        period_text  TEXT,
                        recursos     TEXT,
                        confidence   FLOAT,
                        reasoning    TEXT
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_intents_sid
                    ON session_intents (session_id, created_at DESC)
                """)
        except Exception as exc:
            print(f"[ContextManager] Aviso: não foi possível criar tabela session_intents: {exc}")

    def get_recent(self, session_id: str, limit: int = 10) -> list[ConversationTurn]:
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

    def save_intent(self, session_id: str, ir: InterpretationResult) -> None:
        """
        Persiste o InterpretationResult resolvido no banco N8N.

        Chamado pelo orchestrator após cada execução SQL bem-sucedida.
        Permite que follow-ups usem o intent exato que foi usado — sem
        re-interpretar o texto cru da mensagem anterior.
        """
        try:
            recursos_json = json.dumps(ir.recursos) if ir.recursos is not None else None
            with get_n8n_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO session_intents
                        (session_id, intent, route, metric, entity_type, entity_value,
                         data_inicio, data_fim, period_text, recursos, confidence, reasoning)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id, ir.intent, ir.route, ir.metric,
                        ir.entity_type, ir.entity_value,
                        ir.data_inicio, ir.data_fim, ir.period_text,
                        recursos_json, ir.confidence, ir.reasoning,
                    ),
                )
        except Exception as exc:
            print(f"[ContextManager] Erro ao salvar intent sessão {session_id}: {exc}")

    def get_last_intent(self, session_id: str) -> InterpretationResult | None:
        """
        Retorna o último InterpretationResult resolvido para esta sessão.

        Usado pelo orchestrator para carry-over preciso: em vez de re-interpretar
        o texto das mensagens antigas, usa o intent que foi realmente executado.
        Retorna None se não houver registro ou se o banco estiver inacessível.
        """
        try:
            with get_n8n_conn() as conn:
                row = conn.execute(
                    """
                    SELECT intent, route, metric, entity_type, entity_value,
                           data_inicio, data_fim, period_text, recursos, confidence, reasoning
                    FROM session_intents
                    WHERE session_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (session_id,),
                ).fetchone()

            if not row:
                return None

            recursos = json.loads(row[8]) if row[8] is not None else None
            return InterpretationResult(
                intent=row[0],
                route=row[1],
                metric=row[2],
                entity_type=row[3],
                entity_value=row[4],
                data_inicio=row[5],
                data_fim=row[6],
                period_text=row[7],
                recursos=recursos,
                confidence=float(row[9]) if row[9] is not None else 0.0,
                reasoning=row[10],
            )

        except Exception as exc:
            print(f"[ContextManager] Erro ao buscar intent sessão {session_id}: {exc}")
            return None

    # ── Stubs de escrita (compatibilidade com o orchestrator) ─────────────────
    # A gravação de mensagens é feita pelo backend Node.js — estes métodos
    # existem apenas para evitar erros caso o orchestrator os chame.

    def append_user_message(self, session_id: str, content: str) -> None:
        pass

    def append_assistant_message(self, session_id: str, content: str) -> None:
        pass
