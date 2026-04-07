from typing import Any, Literal
from pydantic import BaseModel, Field


class ChatProcessRequest(BaseModel):
    user_id: str = Field(..., description="Identificador do usuário/canal")
    session_id: str = Field(..., description="Identificador da sessão")
    channel: str = Field(default="web")
    message: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class InterpretationResult(BaseModel):
    intent: str
    route: Literal["sql", "rag", "hybrid", "clarify", "smalltalk"]
    metric: str | None = None
    entity_type: str | None = None
    entity_value: str | None = None
    period_text: str | None = None
    data_inicio: str | None = None   # DD/MM/YYYY
    data_fim: str | None = None      # DD/MM/YYYY
    top_n: int | None = None
    produto_filtro: str | None = None
    setor: str | None = None         # expedicao | revisao | ...
    origem: str | None = None        # SD1 | SD2 | SD3
    confidence: float = 0.0
    reasoning: str | None = None


class ChatProcessResponse(BaseModel):
    status: Literal["ok", "error"]
    answer: str
    route: str
    confidence: float
    used_sql: bool = False
    used_rag: bool = False
    requires_clarification: bool = False
    debug: dict[str, Any] = Field(default_factory=dict)
