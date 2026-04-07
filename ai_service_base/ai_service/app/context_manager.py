from __future__ import annotations

from collections import defaultdict
from app.schemas import ConversationTurn


class InMemoryContextManager:
    """
    Contexto simples em memória para testes locais.
    Em produção, trocar por PostgreSQL/Redis.
    """

    def __init__(self) -> None:
        self._store: dict[str, list[ConversationTurn]] = defaultdict(list)

    def get_recent(self, session_id: str, limit: int = 6) -> list[ConversationTurn]:
        history = self._store.get(session_id, [])
        return history[-limit:]

    def append_user_message(self, session_id: str, content: str) -> None:
        self._store[session_id].append(ConversationTurn(role="user", content=content))

    def append_assistant_message(self, session_id: str, content: str) -> None:
        self._store[session_id].append(ConversationTurn(role="assistant", content=content))
