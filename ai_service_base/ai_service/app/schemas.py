"""
schemas.py — Modelos de dados da API (Pydantic).

Define a estrutura de todos os objetos que entram e saem dos endpoints:

  ChatProcessRequest   → payload enviado pelo frontend para processar uma mensagem
  ChatProcessResponse  → resposta retornada ao frontend após o processamento
  ConversationTurn     → uma mensagem individual no histórico de conversa
  InterpretationResult → resultado interno da análise de intenção (interpreter.py)
"""
from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatProcessRequest(BaseModel):
    """Payload de entrada do endpoint POST /v1/chat/process."""

    user_id: str = Field(..., description="Identificador do usuário autenticado")
    session_id: str = Field(..., description="ID da conversa (UUID gerado pelo frontend)")
    channel: str = Field(default="web", description="Canal de origem: web, mobile, etc.")
    message: str = Field(..., min_length=1, description="Mensagem digitada pelo usuário")

    # Dados do usuário autenticado — enviados pelo frontend para personalizar respostas.
    # O agente recebe essas informações e pode usá-las para saudar pelo nome,
    # contextualizar respostas ao setor, etc.
    user_name: str | None = Field(
        default=None,
        description="Nome completo do usuário autenticado (ex: Pedro Martins)",
    )
    user_setor: str | None = Field(
        default=None,
        description="Departamento do usuário (ex: producao, rh) — usado no controle de acesso LGPD",
    )
    user_cargo: str | None = Field(
        default=None,
        description="Cargo ou função do usuário (opcional — ex: Supervisor de Produção)",
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Dados adicionais opcionais enviados pelo frontend",
    )


class ConversationTurn(BaseModel):
    """Uma mensagem individual no histórico de conversa."""

    role: Literal["user", "assistant", "system"]
    content: str


class InterpretationResult(BaseModel):
    """
    Resultado da análise de intenção produzido pelo RuleBasedInterpreter.
    Usado internamente pelo orchestrator para decidir qual rota executar.
    """

    intent: str                          # ex: "ranking_usuarios_ld", "smalltalk", "clarify"
    route: Literal["sql", "rag", "hybrid", "clarify", "smalltalk"]
    metric: str | None = None            # ex: "geracao_ld", "producao_total"
    entity_type: str | None = None       # "operador" | "produto" | "turno"
    entity_value: str | None = None      # ex: "ezequiel.nunes"
    period_text: str | None = None       # ex: "janeiro de 2026"
    data_inicio: str | None = None       # DD/MM/YYYY
    data_fim: str | None = None          # DD/MM/YYYY
    top_n: int | None = None             # para rankings (ex: top 5)
    produto_filtro: str | None = None    # código do produto (ex: TD2AYBR1BOBR100)
    setor: str | None = None             # "expedicao" | "revisao" | "producao"
    origem: str | None = None            # "SD1" | "SD2" | "SD3"
    recursos: list[str] | None = None    # ["0003"] | ["0007"] | ["0003","0007"] — extrusoras
    confidence: float = 0.0              # confiança da interpretação (0.0–1.0)
    reasoning: str | None = None         # explicação textual da decisão


class ChatProcessResponse(BaseModel):
    """Resposta retornada pelo endpoint para o frontend."""

    status: Literal["ok", "error"]
    answer: str                          # texto da resposta da IA
    route: str                           # rota usada: sql, smalltalk, clarify, etc.
    confidence: float
    used_sql: bool = False               # indica se houve consulta ao banco
    used_rag: bool = False               # reservado para RAG futuro
    requires_clarification: bool = False # sinaliza que a IA pediu reformulação
    debug: dict[str, Any] = Field(default_factory=dict)
