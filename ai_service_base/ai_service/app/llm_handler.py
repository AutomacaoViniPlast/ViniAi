"""
LLM Handler — integração com OpenAI (ChatGPT) para conversação natural.

Responsabilidades:
  - Responder saudações, perguntas gerais e mensagens não identificadas pelo
    interpretador de regras (rota smalltalk / clarify).
  - Manter contexto da conversa usando o histórico de mensagens.
  - Funcionar em modo offline (fallback fixo) quando OPENAI_API_KEY não estiver
    configurada, sem travar o serviço.

Configuração via .env:
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o-mini   # opcional, padrão acima
"""
from __future__ import annotations

import os

from app.schemas import ConversationTurn

# ── System prompt ─────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
Você é o ViniAI, assistente inteligente de dados de produção industrial da Viniplast.

## Contexto da fábrica
- A fábrica produz bobinas plásticas em extrusoras.
- **Produção** = material que saiu da extrusora (operadores da extrusora).
- **Revisão** = inspeção do material após extrusão; identifica LD (defeito) ou Inteiro.
- **Expedição** = liberação de bobinas para clientes (não participam de rankings de produção).
- **LD** = material com defeito (posição 5 do código do produto = "Y").

## Operadores cadastrados
- Revisão: raul.araujo, igor.chiva, ezequiel.nunes
- Expedição: john.moraes, rafael.paiva, andre.prado, richard.santos, arilson.aguiar
- Produção: kaua.chagas (e outros a confirmar)

## Sua personalidade
- Warm, direto e profissional — sem formalidade excessiva.
- Converse em **português do Brasil** de forma natural.
- Responda saudações com naturalidade: "Bom dia!", "Boa tarde!", etc.
- Para perguntas de produção que você não consegue responder (dados do banco), oriente
  o usuário a reformular usando termos como "produção", "LD", "ranking", "turno".
- Para perguntas gerais (clima, notícias, curiosidades), responda brevemente e com
  simpatia, mas mantenha o foco no seu domínio quando possível.
- Não invente números ou dados de produção — eles vêm exclusivamente do banco de dados.
- Respostas concisas: máximo 3 parágrafos. Prefira bullet points quando listar itens.
- Nunca diga que não pode conversar sobre outros assuntos, apenas redirecione com leveza.

## Exemplos de perguntas respondidas via banco de dados
- "Quem gerou mais LD em janeiro?" → ranking de revisão
- "Top 5 de produção em 2025" → ranking de produção
- "Produção por turno em março" → análise de turno
- "Total da fábrica este mês" → agregado geral

Quando o usuário fizer esse tipo de pergunta mas você não tiver os dados na conversa,
diga que pode buscar e peça que ele reformule usando esses termos.\
"""

# ── Mensagens de fallback (modo offline) ─────────────────────────────────────
_FALLBACK_SMALLTALK = (
    "Olá! Sou o **ViniAI**, assistente de produção da Viniplast.\n\n"
    "Posso te ajudar com **LD**, **produção**, **rankings**, **turnos** e mais.\n"
    "Digite *\"o que você sabe fazer?\"* para ver todas as opções."
)

_FALLBACK_CLARIFY = (
    "Não consegui identificar sua solicitação. Tente algo como:\n\n"
    "- *\"Quem mais produziu LD em janeiro de 2026?\"*\n"
    "- *\"Top 5 da revisão com mais LD em 2025\"*\n"
    "- *\"Produção por turno em março de 2026\"*\n"
    "- *\"Total da fábrica este mês\"*"
)


class LLMHandler:
    """
    Gerencia chamadas à API do ChatGPT (OpenAI) para conversação natural.
    Funciona sem chave configurada — retorna respostas fixas de fallback.
    """

    def __init__(self) -> None:
        self._client  = None
        self._model   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._enabled = False
        self._setup()

    def _setup(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            print("[LLMHandler] OPENAI_API_KEY não definida — modo offline (fallback fixo).")
            return

        try:
            from openai import OpenAI
            self._client  = OpenAI(api_key=api_key)
            self._enabled = True
            print(f"[LLMHandler] ChatGPT ativo | modelo: {self._model}")
        except ImportError:
            print(
                "[LLMHandler] Biblioteca 'openai' não instalada.\n"
                "             Execute: pip install openai"
            )

    # ── API pública ───────────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    def respond(
        self,
        message: str,
        history: list[ConversationTurn] | None = None,
        intent: str | None = None,
    ) -> str:
        """
        Gera resposta natural via ChatGPT.

        Parâmetros:
          message : mensagem atual do usuário
          history : histórico recente da conversa (ConversationTurn)
          intent  : intenção identificada pelo RuleBasedInterpreter (para fallback)
        """
        if not self._enabled:
            return self._fallback(intent)

        messages = self._build_messages(history, message)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=512,
                messages=messages,
            )
            return response.choices[0].message.content.strip()

        except Exception as exc:
            print(f"[LLMHandler] Erro na chamada à API: {exc}")
            return self._fallback(intent)

    # ── Internos ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_messages(
        history: list[ConversationTurn] | None,
        current: str,
    ) -> list[dict]:
        """
        Monta lista de mensagens no formato da API OpenAI (system + alternância user/assistant).
        """
        msgs: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

        for turn in (history or []):
            if turn.role in ("user", "assistant"):
                msgs.append({"role": turn.role, "content": turn.content})

        # Remove a última mensagem se já for a atual (evita duplicata)
        if len(msgs) > 1 and msgs[-1]["role"] == "user" and msgs[-1]["content"] == current:
            msgs.pop()

        msgs.append({"role": "user", "content": current})
        return msgs

    @staticmethod
    def _fallback(intent: str | None) -> str:
        if intent == "smalltalk":
            return _FALLBACK_SMALLTALK
        return _FALLBACK_CLARIFY
