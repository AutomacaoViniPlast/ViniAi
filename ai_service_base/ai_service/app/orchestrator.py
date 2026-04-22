"""
orchestrator.py — Orquestrador principal do ViniAI.

Coordena o fluxo completo de processamento de uma mensagem:

  1. Lê o histórico de conversa (context_manager)
  2. Interpreta a intenção da mensagem (interpreter)
  3. Verifica se o usuário tem permissão para aquela consulta (permissions)
     → Se não tiver: retorna mensagem formal de LGPD
  4. Aplica RAG conversacional: se a mensagem for ambígua mas contiver um
     período, reutiliza o intent da última mensagem SQL do histórico.
  5. Injeta automaticamente o login do usuário autenticado quando a intenção
     é sobre o próprio operador (entity_value=None + user_name disponível).
  6. Roteia para o handler correto:
     → smalltalk / clarify  : ChatGPT (llm_handler) responde naturalmente
     → sql                  : SQLService executa a query e formata o resultado

RAG Conversacional (Context Carry-over)
────────────────────────────────────────
  Quando o usuário diz algo como "Quero saber desse mês!" após ter feito uma
  consulta de LD, o orchestrator:
    1. Detecta que o intent atual é clarify com confiança baixa
    2. Verifica se um período foi extraído da mensagem
    3. Busca no histórico a última mensagem SQL completa do usuário
    4. Reutiliza esse intent com o novo período (carry-over)
  Isso evita que o LLM "esqueça" o contexto e recomece a conversa do zero.

Regra de importações (anti-circular):
  agents → sem deps internas
  config → sem deps internas
  sql_service → importa só db
  interpreter → importa config, schemas
  permissions → sem deps internas
  orchestrator → importa tudo acima + context_manager + llm_handler
  main → importa orchestrator
"""
from __future__ import annotations

import re

from app.agents import get_agent
from app.config import (
    OPERADORES_ATIVOS, ORIGENS,
    get_label_setor, get_operadores_setor, get_setor_de, todos_operadores,
)
from app.context_manager import PostgresContextManager
from app.interpreter import InterpretationResult, RuleBasedInterpreter, _periodo_from_text
from app.llm_handler import LLMHandler
from app.permissions import MENSAGEM_LGPD, verificar_permissao
from app.schemas import ChatProcessRequest, ChatProcessResponse, ConversationTurn
from app.sql_service_kardex import SQLServiceKardex
from app.sql_service_sh6 import SQLServiceSH6, traduzir_recurso, traduzir_filial


# ── Helpers de formatação ─────────────────────────────────────────────────────

def _fmt_kg(valor: float) -> str:
    """Formata um valor float para exibição em KG no padrão brasileiro."""
    return f"{valor:,.2f} KG".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_quantidade(resultado: dict) -> str:
    """Formata resultado de QUANTIDADE separado por UM (retorno do KARDEX). Omite unidades zeradas."""
    from decimal import Decimal
    partes = []
    for um in ("KG", "MT"):
        val = float(resultado.get(um, 0))
        if val > 0:
            fmt = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            partes.append(f"{fmt} {um}")
    return " | ".join(partes) if partes else "0"


def _posicao_label(pos: int) -> str:
    """Retorna emoji de medalha para top 3 e numeração para os demais."""
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"{pos}°")


def _periodo_label(ir: InterpretationResult) -> str:
    """Gera o trecho textual do período para exibição na resposta."""
    if ir.period_text:
        return f" em {ir.period_text}"
    if ir.data_inicio and ir.data_fim:
        return f" de {ir.data_inicio} a {ir.data_fim}"
    return ""


def _origem_label(origem: str | None) -> str:
    """Gera o trecho textual do tipo de movimentação (ex: ' [Entrada]')."""
    if not origem:
        return ""
    nome = ORIGENS.get(origem, origem)
    return f" [{nome}]"


def _user_login_from_name(user_name: str | None) -> str | None:
    """
    Tenta mapear o nome do usuário autenticado para um login de operador.

    Exemplos:
      "Ezequiel Nunes" → "ezequiel.nunes"
      "Tales"          → None (não é operador cadastrado)
      "igor"           → "igor.chiva"

    Busca pelo primeiro nome ou nome completo contra todos os operadores cadastrados.
    """
    if not user_name:
        return None

    # Se já está no formato login (ex: "ezequiel.nunes"), retorna direto
    if "." in user_name and user_name.lower() in todos_operadores():
        return user_name.lower()

    # Busca por primeiro nome ou nome completo nos operadores cadastrados
    for operador in todos_operadores():
        primeiro_nome = operador.split(".")[0]
        if re.search(rf"\b{re.escape(primeiro_nome)}\b", user_name, re.IGNORECASE):
            return operador

    return None


# ── Orquestrador ──────────────────────────────────────────────────────────────

class ChatOrchestrator:
    """
    Processa mensagens do usuário e retorna respostas formatadas.

    Parâmetros:
      agent_id : ID do agente ativo (padrão: "producao" → Ayla).
                 Deve corresponder a uma chave em agents.py.
    """

    def __init__(self, agent_id: str = "producao") -> None:
        agent             = get_agent(agent_id)
        self.agent_id     = agent_id
        self.agent_name   = agent["name"]
        self.capabilities = agent.get("capabilities", "")
        self.context      = PostgresContextManager()
        self.interpreter  = RuleBasedInterpreter()
        self.sql          = SQLServiceSH6()
        self.kardex       = SQLServiceKardex()
        self.llm          = LLMHandler(
            agent_name=agent["name"],
            system_prompt=agent["system_prompt"],
        )

    # ── Ponto de entrada ──────────────────────────────────────────────────────

    def process(self, payload: ChatProcessRequest) -> ChatProcessResponse:
        """Processa uma mensagem e retorna a resposta do agente."""

        # 1. Lê o histórico para passar ao LLM como contexto
        self.context.append_user_message(payload.session_id, payload.message)
        recent = self.context.get_recent(payload.session_id, limit=32)

        # 2. Resolve campos do usuário — topo do payload tem prioridade;
        #    fallback para metadata (compatibilidade com N8N que envia via metadata)
        user_name  = payload.user_name  or payload.metadata.get("userName") or payload.metadata.get("user_name")
        user_setor = payload.user_setor or payload.metadata.get("setor")    or payload.metadata.get("user_setor")
        user_cargo = payload.user_cargo or payload.metadata.get("cargo")    or payload.metadata.get("user_cargo")

        # 3. Interpreta a intenção da mensagem
        ir = self.interpreter.interpret(payload.message)

        # 4. Verifica permissão LGPD
        if not verificar_permissao(user_setor, self.agent_id, ir.intent):
            self.context.append_assistant_message(payload.session_id, MENSAGEM_LGPD)
            return self._ok(MENSAGEM_LGPD, ir)

        # ── 4a. Capacidades do agente ("o que você faz?") ─────────────────────
        if ir.intent == "tipos_informacao":
            answer = self.capabilities or (
                f"Sou a **{self.agent_name}** e posso responder consultas do meu domínio. "
                "Tente perguntar sobre produção, LD, rankings ou turnos."
            )
            self.context.append_assistant_message(payload.session_id, answer)
            return self._ok(answer, ir)

        # ── 4b. RAG Conversacional — context carry-over ───────────────────────
        # Extrai período explícito da mensagem atual (None se não mencionado)
        msg_ini, msg_fim, msg_lbl = _periodo_from_text(payload.message)
        periodo_explicito = bool(msg_ini or msg_fim)

        # Caso 1: mensagem ambígua com período novo → herda intent do histórico
        # Ex: "Quero saber de janeiro!" após consulta de LD
        if ir.route in ("clarify", "smalltalk") and ir.confidence < 0.75 and periodo_explicito:
            followup_ir = self._try_context_followup(recent, msg_ini, msg_fim, msg_lbl)
            if followup_ir:
                ir = followup_ir
                print(f"[{self.agent_name}] RAG carry-over: reutilizando intent '{ir.intent}' com novo período.")

        # Caso 4: mensagem ambígua sem período mas com recurso → herda intent + período do histórico
        # Ex: "E da MAC2?" após "Produção da MAC1 e 2 ontem?" — sem período, mas menciona recurso
        # Sem este caso, o LLM responde com valor inventado baseado no histórico (alucinação)
        elif ir.route in ("clarify", "smalltalk") and ir.confidence < 0.75 and not periodo_explicito:
            recurso_novo = self.interpreter._extract_recurso(payload.message)
            if recurso_novo:
                followup_ir = self._try_context_followup(recent, None, None, None, recursos_new=recurso_novo)
                if followup_ir:
                    ir = followup_ir
                    print(f"[{self.agent_name}] RAG recurso-carry (clarify): reutilizando intent '{ir.intent}' com recurso {recurso_novo}.")

        # Caso 3: SQL genérico sem operador → follow-up de recurso/extrusora
        # Ex: "E na extrusora 2?" após consulta de KGH herda intent kgh + atualiza recurso
        elif (
            ir.route == "sql"
            and ir.intent == "producao_por_operador"
            and not ir.entity_value
            and ir.confidence < 0.75
        ):
            followup_ir = self._try_context_followup(
                recent, msg_ini, msg_fim, msg_lbl, recursos_new=ir.recursos,
            )
            if followup_ir:
                ir = followup_ir
                print(f"[{self.agent_name}] RAG recurso-carry: reutilizando intent '{ir.intent}' com novo recurso.")

        # Caso 2: consulta SQL sem período explícito → herda período do histórico
        # Ex: "E o do Igor?" após "Qual o LD do Ezequiel em janeiro?" herda janeiro
        # Também ativa para mensagens curtas (≤ 5 palavras) mesmo com alta confiança —
        # evita que "E da extrusora 1?" use período padrão ao invés de herdar "ontem"
        elif ir.route == "sql" and not periodo_explicito and (
            ir.confidence < 0.87 or len(payload.message.strip().split()) <= 5
        ):
            inherited = self._inherit_period_from_history(recent)
            if inherited:
                ir.data_inicio, ir.data_fim, ir.period_text = inherited
                print(
                    f"[{self.agent_name}] period-inherit: "
                    f"'{inherited[2]}' herdado do histórico (conf={ir.confidence:.2f})."
                )

        # ── 4c. Conversação natural → LLM ────────────────────────────────────
        if ir.route in ("smalltalk", "clarify"):
            user_context = {"name": user_name, "setor": user_setor, "cargo": user_cargo}
            print(f"[{self.agent_name}] user_context recebido: {user_context}")
            answer = self.llm.respond(
                message=payload.message,
                history=recent,
                intent=ir.intent,
                user_context=user_context,
            )
            self.context.append_assistant_message(payload.session_id, answer)
            requires_clarification = ir.route == "clarify"
            resp = self._ok(answer, ir, requires_clarification=requires_clarification)
            resp.debug["user_context_received"] = user_context
            return resp

        # ── 4d. Auto-inject: quando intent é de operador mas nenhum foi ───────
        #        extraído do texto, usa o próprio usuário autenticado.
        #        Evita pedir o nome de quem já está logado.
        if (
            ir.intent in ("geracao_ld_por_operador", "producao_por_operador")
            and not ir.entity_value
        ):
            user_login = _user_login_from_name(user_name)
            if user_login:
                ir.entity_value = user_login
                print(f"[{self.agent_name}] Auto-inject: entity_value='{user_login}' (usuário autenticado).")

        # ── 4e. Consulta ao banco de dados → SQL ─────────────────────────────
        answer = self._handle_sql(ir)
        self.context.append_assistant_message(payload.session_id, answer)
        return ChatProcessResponse(
            status="ok",
            answer=answer,
            route=ir.route,
            confidence=ir.confidence,
            used_sql=True,
            debug={
                "agent":        self.agent_name,
                "intent":       ir.intent,
                "metric":       ir.metric,
                "entity_type":  ir.entity_type,
                "entity_value": ir.entity_value,
                "period_text":  ir.period_text,
                "data_inicio":  ir.data_inicio,
                "data_fim":     ir.data_fim,
                "top_n":        ir.top_n,
                "setor":        ir.setor,
                "origem":       ir.origem,
                "history_size":      len(recent),
                "reasoning":         ir.reasoning,
                "user_setor":        user_setor,
                "user_name":         user_name,
                "periodo_explicito": periodo_explicito,
            },
        )

    # ── RAG Conversacional ────────────────────────────────────────────────────

    def _try_context_followup(
        self,
        recent: list[ConversationTurn],
        ini_new: str | None,
        fim_new: str | None,
        lbl_new: str | None,
        recursos_new: list[str] | None = None,
    ) -> InterpretationResult | None:
        """
        RAG conversacional: quando a mensagem atual só especifica um período
        sem intent claro, reutiliza o intent SQL da última mensagem completa
        do histórico — combinando a entidade (operador) de clarificações curtas.

        Estratégia:
          1. Varre o histórico em ordem reversa (mais recente primeiro).
          2. Extrai operador de mensagens curtas (clarificações como "Ezequiel").
          3. Busca a última mensagem "completa" (> 3 palavras) com intent SQL.
          4. Aplica: entidade da clarificação + intent da mensagem completa + novo período.

        Exemplo:
          Histórico: ["Qual foi o LD nesse mês?", "Ezequiel", "Quero saber desse mês!"]
          Resultado: intent=geracao_ld_por_operador, entity=ezequiel.nunes, período=atual
        """
        user_msgs = [t.content for t in reversed(recent) if t.role == "user"]

        if not user_msgs:
            return None

        # Passo 1: extrai operador de mensagens curtas (clarificações de nome)
        entity_override: str | None = None
        for msg in user_msgs:
            if len(msg.strip().split()) <= 3:
                op = self.interpreter._extract_operator(msg)
                if op:
                    entity_override = op
                    break

        # Passo 2: busca a última mensagem "completa" com intent SQL claro
        for msg in user_msgs:
            if len(msg.strip().split()) <= 3:
                continue  # pula clarificações curtas

            prev_ir = self.interpreter.interpret(msg)
            if prev_ir.route == "sql" and prev_ir.confidence >= 0.55:
                # Aplica entidade clarificada (ex: "Ezequiel" dito depois)
                if entity_override and not prev_ir.entity_value:
                    prev_ir.entity_value = entity_override

                # Aplica novo período mantendo o restante do contexto
                if ini_new:
                    prev_ir.data_inicio = ini_new
                if fim_new:
                    prev_ir.data_fim = fim_new
                if lbl_new:
                    prev_ir.period_text = lbl_new
                # Aplica recurso novo (ex: "E na extrusora 2?" atualiza de 0003 para 0007)
                if recursos_new:
                    prev_ir.recursos = recursos_new

                prev_ir.route     = "sql"
                prev_ir.reasoning = f"[context-carry] {prev_ir.reasoning}"
                return prev_ir

        return None

    # ── Herança de Período ────────────────────────────────────────────────────

    def _inherit_period_from_history(
        self,
        recent: list[ConversationTurn],
        max_lookback: int = 6,
    ) -> tuple[str, str, str] | None:
        """
        Herda o período da última mensagem do usuário que continha um período explícito.

        Usado quando a mensagem atual é uma consulta SQL clara mas sem período
        especificado — ex: "E o do Igor?" após "Qual o LD do Ezequiel em janeiro?".
        Nesse caso, herda 'janeiro' em vez de usar o período padrão (mês atual).

        Parâmetros:
          recent       : histórico recente (ConversationTurn)
          max_lookback : limita quantas mensagens atrás pesquisar (padrão: 6)

        Retorna (data_inicio, data_fim, period_text) ou None se não encontrar.
        """
        user_msgs = [t.content for t in reversed(recent) if t.role == "user"]
        for msg in user_msgs[:max_lookback]:
            ini, fim, lbl = _periodo_from_text(msg)
            if ini and fim:
                return ini, fim, lbl
        return None

    # ── Handler SQL ───────────────────────────────────────────────────────────

    def _handle_sql(self, ir: InterpretationResult) -> str:
        try:
            return self._dispatch(ir)
        except Exception as exc:
            return f"Ocorreu um erro ao consultar o banco de dados: {exc}"

    @staticmethod
    def _is_diaria(ir: InterpretationResult) -> bool:
        """Consulta diária quando período é um único dia (ini == fim)."""
        return bool(ir.data_inicio and ir.data_fim and ir.data_inicio == ir.data_fim)

    @staticmethod
    def _recurso_label(recursos: list[str] | None) -> str:
        """Gera sufixo legível para o recurso filtrado."""
        if not recursos:
            return ""
        labels = [traduzir_recurso(r) for r in recursos]
        return f" [{', '.join(labels)}]"

    def _dispatch(self, ir: InterpretationResult) -> str:  # noqa: C901
        """Despacha o intent para a query SH6 correspondente e formata a resposta."""

        periodo   = _periodo_label(ir)
        ini       = ir.data_inicio
        fim       = ir.data_fim
        top_n     = ir.top_n or 5
        recursos  = ir.recursos  # None = ambas extrusoras (default no service)
        is_diaria = self._is_diaria(ir)
        rec_lbl   = self._recurso_label(recursos)

        # ── Listar operadores de um setor ─────────────────────────────────────
        if ir.intent == "list_operadores_revisao":
            alvo  = ir.setor or "revisao"
            ops   = get_operadores_setor(alvo)
            label = get_label_setor(alvo)
            if not ops:
                return f"Nenhum operador cadastrado para o setor {label}."
            linhas = "\n".join(f"- {op}" for op in ops)
            return f"👥 **Operadores da {label}**\n\n{linhas}"

        # ── Total geral da fábrica (SH6) ──────────────────────────────────────
        if ir.intent == "total_fabrica":
            total = self.sql.get_producao_total(ini, fim, recursos=recursos, is_diaria=is_diaria)
            if float(total) == 0:
                return f"🔍 Nenhum dado de produção encontrado{periodo}{rec_lbl}."
            tipo = "dia" if is_diaria else "mês"
            return (
                f"🏭 **Produção total da fábrica — {tipo}**{periodo}{rec_lbl}\n\n"
                f"| Métrica | Valor |\n|---------|-------|\n"
                f"| ⚙️ Total geral | **{_fmt_kg(float(total))}** |"
            )

        # ── Ranking de produção por operador (SH6) ────────────────────────────
        if ir.intent == "ranking_producao_geral":
            rows = self.sql.get_ranking_producao(ini, fim, top_n, recursos=recursos, is_diaria=is_diaria)
            if not rows:
                return f"🔍 Nenhum dado encontrado{periodo}{rec_lbl}."
            header = f"🏆 **Top {top_n} — Produção**{periodo}{rec_lbl}\n\n"
            header += "| # | Operador | Total |\n|---|----------|-------|\n"
            linhas = "\n".join(
                f"| {_posicao_label(r['posicao'])} | {r['operador']} | **{_fmt_kg(r['total_kg'])}** |"
                for r in rows
            )
            return header + linhas

        # ── Comparativo entre extrusoras (SH6) ───────────────────────────────
        if ir.intent == "comparativo_extrusoras":
            rows = self.sql.get_producao_por_recurso(ini, fim, recursos=recursos, is_diaria=is_diaria)
            if not rows:
                return f"🔍 Nenhum dado encontrado{periodo}{rec_lbl}."
            header = f"⚙️ **Comparativo de produção por extrusora**{periodo}\n\n"
            header += "| Extrusora | Total KG | Registros |\n|-----------|----------|----------|\n"
            linhas = "\n".join(
                f"| {r['recurso_label']} | **{_fmt_kg(r['total_kg'])}** | {r['registros']} |"
                for r in rows
            )
            # Calcula diferença se houver exatamente 2 máquinas
            if len(rows) == 2:
                diff = abs(rows[0]["total_kg"] - rows[1]["total_kg"])
                lider = rows[0]["recurso_label"] if rows[0]["total_kg"] >= rows[1]["total_kg"] else rows[1]["recurso_label"]
                linhas += f"\n\n> **{lider}** produziu **{_fmt_kg(diff)}** a mais no período."
            return header + linhas

        # ── Horas trabalhadas por extrusora (SH6) ─────────────────────────────
        if ir.intent == "horas_trabalhadas":
            rows = self.sql.get_horas_trabalhadas(ini, fim, recursos=recursos, is_diaria=is_diaria)
            if not rows:
                return f"🔍 Nenhum dado de horas encontrado{periodo}{rec_lbl}."
            header = f"⏱️ **Horas trabalhadas**{periodo}{rec_lbl}\n\n"
            header += "| Extrusora | Horas | Minutos |\n|-----------|-------|--------|\n"
            linhas = "\n".join(
                f"| {r['recurso_label']} | **{r['horas']:,.2f} h** | {r['minutos']:,.0f} min |"
                for r in rows
            )
            return header + linhas

        # ── Produção por operador específico (SH6) ────────────────────────────
        if ir.intent == "producao_por_operador":
            if not ir.entity_value:
                return "❓ Não consegui identificar o operador. Informe o nome completo ou login."
            total = self.sql.get_producao_por_operador(
                ir.entity_value, ini, fim, recursos=recursos, is_diaria=is_diaria,
            )
            if float(total) == 0:
                return (
                    f"🔍 Nenhum registro encontrado para **{ir.entity_value}**{periodo}{rec_lbl}.\n\n"
                    "Verifique o nome ou o período informado."
                )
            tipo = "dia" if is_diaria else "mês"
            return (
                f"⚙️ **Produção — {ir.entity_value}**\n\n"
                f"📅 Período ({tipo}): {periodo.strip() or 'geral'}{rec_lbl}\n"
                f"⚖️ Total: **{_fmt_kg(float(total))}**"
            )

        # ── Metros por minuto (SH6) ───────────────────────────────────────────
        if ir.intent == "metros_por_minuto":
            data = self.sql.get_metros_por_minuto(ini, fim, recursos=recursos, is_diaria=is_diaria)
            if data["resultado"] == 0:
                return f"🔍 Nenhum dado de metros/min encontrado{periodo}{rec_lbl}."
            return (
                f"📏 **Metros por minuto**{periodo}{rec_lbl}\n\n"
                f"| Métrica | Valor |\n|---------|-------|\n"
                f"| Metros totais | {data['metros']:,.2f} m |\n"
                f"| Minutos totais | {data['minutos']:,.0f} min |\n"
                f"| **Média m/min** | **{data['resultado']:.4f}** |"
            )

        # ── KGH — KG por hora (SH6) ───────────────────────────────────────────
        if ir.intent == "kgh":
            rows = self.sql.get_kgh(ini, fim, recursos=recursos, is_diaria=is_diaria)
            if not rows:
                return f"🔍 Nenhum dado de KGH encontrado{periodo}{rec_lbl}."
            blocos = []
            for r in rows:
                bloco = (
                    f"**{r['recurso_label']}**\n\n"
                    f"| Métrica | Valor |\n|---------|-------|\n"
                    f"| KG total | {r['total_kg']:,.2f} KG |\n"
                    f"| Horas totais | {r['horas']:,.2f} h |\n"
                    f"| **KGH** | **{r['kgh']:,.2f}** |"
                )
                blocos.append(bloco)
            header = f"⚡ **KG/hora por extrusora**{periodo}{rec_lbl}\n\n"
            return header + "\n\n".join(blocos)

        # ── Intents KARDEX — consultas que envolvem qualidade do material ────────

        # ── LD do próprio usuário ou de operador específico (KARDEX) ─────────────
        if ir.intent == "geracao_ld_por_operador":
            if ir.entity_value:
                resultado = self.kardex.get_ld_por_operador(ir.entity_value, ini, fim)
                total_str = _fmt_quantidade(resultado)
                if all(float(v) == 0 for v in resultado.values()):
                    return f"🔍 Nenhum LD registrado para **{ir.entity_value}**{periodo}."
                tipo = "dia" if is_diaria else "mês"
                return (
                    f"⚠️ **LD — {ir.entity_value}**\n\n"
                    f"📅 Período ({tipo}): {periodo.strip() or 'geral'}\n"
                    f"📦 Total LD: **{total_str}**"
                )
            else:
                # Sem operador específico — total geral de LD dos operadores ativos
                resultado = self.kardex.get_ld_total(ini, fim, filtro_usuarios=OPERADORES_ATIVOS)
                total_str = _fmt_quantidade(resultado)
                if all(float(v) == 0 for v in resultado.values()):
                    return f"🔍 Nenhum LD registrado{periodo}."
                tipo = "dia" if is_diaria else "mês"
                return (
                    f"⚠️ **Total de LD**{periodo}\n\n"
                    f"| Métrica | Valor |\n|---------|-------|\n"
                    f"| 📦 Total LD | **{total_str}** |"
                )

        # ── Ranking de operadores com mais LD (KARDEX) ────────────────────────────
        if ir.intent == "ranking_usuarios_ld":
            rows = self.kardex.get_ranking_ld(
                ini, fim, limite=top_n,
                recursos=recursos,
                filtro_usuarios=OPERADORES_ATIVOS,
            )
            if not rows:
                return f"🔍 Nenhum dado de LD encontrado{periodo}{rec_lbl}."
            unidade = rows[0]["unidade"] if rows else "KG"
            header = f"⚠️ **Top {top_n} — LD por operador**{periodo}{rec_lbl}\n\n"
            header += f"| # | Operador | Total {unidade} |\n|---|----------|----------|\n"
            linhas = "\n".join(
                f"| {_posicao_label(r['posicao'])} | {r['operador']} | **{_fmt_kg(r['total'])}** |"
                for r in rows
            )
            return header + linhas

        # ── Ranking de produtos com mais LD (KARDEX) ──────────────────────────────
        if ir.intent == "ranking_produtos_ld":
            rows = self.kardex.get_ranking_produtos_ld(
                ini, fim, limite=top_n,
                filtro_usuarios=OPERADORES_ATIVOS,
            )
            if not rows:
                return f"🔍 Nenhum dado de LD por produto encontrado{periodo}."
            header = f"⚠️ **Top {top_n} — Produtos com mais LD**{periodo}\n\n"
            header += "| # | Produto | Descrição | Total | Ocorrências |\n|---|---------|-----------|-------|-------------|\n"
            linhas = "\n".join(
                f"| {_posicao_label(r['posicao'])} | {r['produto']} | {r['descricao'] or '-'} "
                f"| **{_fmt_kg(r['total'])}** | {r['ocorrencias']} |"
                for r in rows
            )
            return header + linhas

        return "Solicitação recebida, mas ainda não há tratativa para este tipo de consulta."

    # ── Helper de resposta ────────────────────────────────────────────────────

    def _ok(
        self,
        answer: str,
        ir: InterpretationResult,
        requires_clarification: bool = False,
    ) -> ChatProcessResponse:
        return ChatProcessResponse(
            status="ok",
            answer=answer,
            route=ir.route,
            confidence=ir.confidence,
            requires_clarification=requires_clarification,
            debug={
                "agent":     self.agent_name,
                "intent":    ir.intent,
                "reasoning": ir.reasoning,
            },
        )
