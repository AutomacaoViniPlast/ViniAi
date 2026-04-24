"""
LLM Handler — integração com OpenAI (ChatGPT) para conversação natural.

Responsabilidades:
  - Responder saudações, perguntas gerais e mensagens não identificadas pelo
    interpretador de regras (rota smalltalk / clarify).
  - Manter contexto da conversa usando o histórico de mensagens.
  - Funcionar em modo offline (fallback fixo) quando OPENAI_API_KEY não estiver
    configurada, sem travar o serviço.
  - Suportar múltiplos agentes: recebe o system_prompt do agente ativo.

Configuração via .env:
  OPENAI_API_KEY=sk-...
  OPENAI_MODEL=gpt-4o-mini   # opcional, padrão acima
"""
from __future__ import annotations

import os
from datetime import date

from app.schemas import ConversationTurn

# Mapeamento de weekday para português
_DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira",
    "quinta-feira", "sexta-feira", "sábado", "domingo",
]


class LLMHandler:
    """
    Gerencia chamadas à API do ChatGPT (OpenAI) para conversação natural.
    Funciona sem chave configurada — retorna respostas fixas de fallback.

    O system_prompt é definido pelo agente ativo (agents.py) e passado
    no momento da instanciação, permitindo múltiplos agentes com personalidades distintas.
    """

    def __init__(self, agent_name: str = "Ayla", system_prompt: str = "") -> None:
        self._agent_name   = agent_name
        self._system_prompt = system_prompt
        self._client        = None
        self._model         = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._enabled       = False
        self._setup()

    def _setup(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            print(f"[{self._agent_name}] OPENAI_API_KEY não definida — modo offline (fallback fixo).")
            return

        try:
            from openai import OpenAI
            self._client  = OpenAI(api_key=api_key)
            self._enabled = True
            print(f"[{self._agent_name}] ChatGPT ativo | modelo: {self._model}")
        except ImportError:
            print(
                f"[{self._agent_name}] Biblioteca 'openai' não instalada.\n"
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
        user_context: dict | None = None,
    ) -> str:
        """
        Gera resposta natural via ChatGPT.

        Parâmetros:
          message      : mensagem atual do usuário
          history      : histórico recente da conversa (ConversationTurn)
          intent       : intenção identificada pelo RuleBasedInterpreter (para fallback)
          user_context : dados do usuário autenticado — injetados no system prompt
                         para que o agente saiba com quem está conversando.
                         Campos aceitos: name, setor, cargo
        """
        if not self._enabled:
            return self._fallback(intent)

        # Monta o system prompt: âncora temporal + base do agente + bloco do usuário
        today = date.today()
        dia_semana = _DIAS_SEMANA[today.weekday()]
        date_header = (
            f"**Data de hoje:** {today.strftime('%d/%m/%Y')} ({dia_semana})\n"
            f"Use essa data como referência absoluta para \"hoje\", \"este mês\", "
            f"\"este ano\", etc. NUNCA invente ou assuma datas sem usar este valor.\n"
        )
        system = date_header + "\n" + self._system_prompt
        if user_context:
            system = system + "\n\n" + self._build_user_block(user_context)

        messages = self._build_messages(system, history, message)

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=512,
                messages=messages,
            )
            return response.choices[0].message.content.strip()

        except Exception as exc:
            print(f"[{self._agent_name}] Erro na chamada à API: {exc}")
            return self._fallback(intent)

    # ── Internos ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_user_block(user_context: dict) -> str:
        """
        Monta um bloco de texto com os dados do usuário autenticado para injeção
        no system prompt — assim o agente sabe com quem está conversando.
        """
        lines = ["## Usuário atual"]
        if user_context.get("name"):
            lines.append(f"- **Nome:** {user_context['name']}")
        if user_context.get("setor"):
            lines.append(f"- **Departamento:** {user_context['setor']}")
        if user_context.get("cargo"):
            lines.append(f"- **Cargo:** {user_context['cargo']}")
        lines.append(
            "\nUse essas informações para saudar o usuário pelo nome e personalizar "
            "a conversa ao contexto do departamento dele."
        )
        return "\n".join(lines)

    @staticmethod
    def _build_messages(
        system_prompt: str,
        history: list[ConversationTurn] | None,
        current: str,
    ) -> list[dict]:
        """
        Monta lista de mensagens no formato da API OpenAI (system + alternância user/assistant).
        """
        msgs: list[dict] = [{"role": "system", "content": system_prompt}]

        for turn in (history or []):
            if turn.role in ("user", "assistant"):
                msgs.append({"role": turn.role, "content": turn.content})

        # Remove a última mensagem se já for a atual (evita duplicata)
        if len(msgs) > 1 and msgs[-1]["role"] == "user" and msgs[-1]["content"] == current:
            msgs.pop()

        msgs.append({"role": "user", "content": current})
        return msgs

    def _fallback(self, intent: str | None) -> str:
        if intent == "smalltalk":
            return (
                f"Olá! Sou a **{self._agent_name}**, assistente de produção da Viniplast. 👋\n\n"
                "Posso buscar dados de **LD**, **produção**, **rankings**, **turnos** e **expedição**.\n\n"
                "O que você precisa?"
            )
        return (
            "Não consegui identificar exatamente o que você precisa. Pode reformular?\n\n"
            "Alguns exemplos do que posso buscar:\n\n"
            "- *\"Quem mais gerou LD em janeiro de 2026?\"*\n"
            "- *\"Top 5 de produção em 2025\"*\n"
            "- *\"Produção por turno em março\"*\n"
            "- *\"Total da fábrica este mês\"*\n\n"
            "Se quiser saber tudo que posso fazer, é só perguntar *\"o que você consegue?\"*"
        )
