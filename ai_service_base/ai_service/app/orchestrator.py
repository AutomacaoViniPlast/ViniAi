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
from app.sql_service import SQLService


# ── Helpers de formatação ─────────────────────────────────────────────────────

def _fmt_kg(valor: float) -> str:
    """Formata um valor float para exibição em KG no padrão brasileiro."""
    return f"{valor:,.2f} KG".replace(",", "X").replace(".", ",").replace("X", ".")


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
        self.sql          = SQLService()
        self.llm          = LLMHandler(
            agent_name=agent["name"],
            system_prompt=agent["system_prompt"],
        )

    # ── Ponto de entrada ──────────────────────────────────────────────────────

    def process(self, payload: ChatProcessRequest) -> ChatProcessResponse:
        """Processa uma mensagem e retorna a resposta do agente."""

        # 1. Lê o histórico para passar ao LLM como contexto
        self.context.append_user_message(payload.session_id, payload.message)
        recent = self.context.get_recent(payload.session_id, limit=16)

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

        # Caso 2: consulta SQL sem período explícito → herda período do histórico
        # Ex: "E o do Igor?" após "Qual o LD do Ezequiel em janeiro?" herda janeiro
        elif ir.route == "sql" and not periodo_explicito and ir.confidence < 0.87:
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

    def _dispatch(self, ir: InterpretationResult) -> str:  # noqa: C901
        """Despacha o intent para a query SQL correspondente e formata a resposta."""

        periodo  = _periodo_label(ir)
        orig_lbl = _origem_label(ir.origem)
        ini      = ir.data_inicio
        fim      = ir.data_fim
        top_n    = ir.top_n or 5
        origem   = ir.origem
        setor    = ir.setor

        # Setor explícito → filtra aquele setor; sem setor → usa OPERADORES_ATIVOS
        if setor:
            filtro_usuarios = get_operadores_setor(setor)
            setor_label     = get_label_setor(setor)
        else:
            filtro_usuarios = list(OPERADORES_ATIVOS)
            setor_label     = None

        # ── Períodos disponíveis ──────────────────────────────────────────────
        if ir.intent == "periodos_disponiveis":
            _MESES_NOME = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
            periodos = self.sql.get_periodos_disponiveis(filtro_usuarios)
            if not periodos:
                return "Não encontrei dados no banco para os operadores ativos."

            linhas, avisos = [], []
            for p in periodos:
                ano, meses = p["ano"], p["meses"]
                if meses == list(range(1, 13)):
                    linhas.append(f"- **{ano}**: ano completo (Jan–Dez)")
                else:
                    nomes = ", ".join(_MESES_NOME[m - 1] for m in meses)
                    linhas.append(f"- **{ano}**: {nomes}")
                    if len(meses) < 6:
                        avisos.append(f"{ano} (dados esparsos — {len(meses)} meses)")

            nota = ""
            if avisos:
                nota = "\n\n> Dados incompletos em: " + ", ".join(avisos)
            nota += "\n\n> Para consultas confiáveis, recomendo usar **2022 em diante**."
            return "### Períodos com dados disponíveis\n\n" + "\n".join(linhas) + nota

        # ── Listar operadores de um setor ─────────────────────────────────────
        if ir.intent == "list_operadores_revisao":
            alvo  = ir.setor or "revisao"
            ops   = get_operadores_setor(alvo)
            label = get_label_setor(alvo)
            if not ops:
                return f"Nenhum operador cadastrado para o setor {label}."
            encontrados = self.sql.get_review_operators(ops)
            linhas  = "\n".join(f"- {op}" for op in ops)
            sem_reg = [o for o in ops if o not in encontrados]
            nota = f"\n\n> Sem registros no banco: {', '.join(sem_reg)}" if sem_reg else ""
            return f"### Operadores da {label}\n\n{linhas}{nota}"

        # ── Ranking de revisão por LD ─────────────────────────────────────────
        if ir.intent == "ranking_usuarios_ld":
            rows = self.sql.get_ranking_usuarios_ld(
                ini, fim, top_n, origem, filtro_usuarios=filtro_usuarios,
            )
            if not rows:
                contexto = f" da {setor_label}" if setor_label else ""
                return f"Nenhum dado de LD encontrado{contexto}{periodo}{orig_lbl}."
            contexto = f" da {setor_label}" if setor_label else ""
            header = f"### Top {top_n} — Revisão de LD{contexto}{periodo}{orig_lbl}\n\n"
            header += "| # | Operador | Total |\n|---|----------|-------|\n"
            linhas = "\n".join(
                f"| {r['posicao']}º | {r['operador']} | **{_fmt_kg(r['total_kg'])}** |"
                for r in rows
            )
            return header + linhas

        # ── Ranking de produtos por LD ────────────────────────────────────────
        if ir.intent == "ranking_produtos_ld":
            rows = self.sql.get_ranking_produtos_ld(
                ini, fim, top_n, origem, filtro_usuarios=filtro_usuarios,
            )
            if not rows:
                return f"Nenhum produto com LD encontrado{periodo}{orig_lbl}."
            header = f"### Top {top_n} — Produtos com mais LD{periodo}{orig_lbl}\n\n"
            header += "| # | Produto | Total | Registros |\n|---|---------|-------|-----------|\n"
            linhas = "\n".join(
                f"| {r['posicao']}º | `{r['produto']}` | **{_fmt_kg(r['total_kg'])}** | {r['ocorrencias']} |"
                for r in rows
            )
            return header + linhas

        # ── LD por operador específico ─────────────────────────────────────────
        if ir.intent == "geracao_ld_por_operador":
            if not ir.entity_value:
                return (
                    "Não consegui identificar o operador. "
                    "Informe o nome (ex: *ezequiel.nunes* ou só *'Ezequiel'*) "
                    "ou pergunte como *'meu LD'* se for sobre você mesmo."
                )
            setor_op   = get_setor_de(ir.entity_value)
            setor_info = f" ({get_label_setor(setor_op)})" if setor_op else ""
            total = self.sql.get_ld_por_operador(ir.entity_value, ini, fim, origem)
            if float(total) == 0:
                return (
                    f"Nenhum LD identificado por **{ir.entity_value}**{setor_info}{periodo}{orig_lbl}.\n"
                    "Verifique o nome ou o período informado."
                )
            return (
                f"### LD identificado em revisão\n\n"
                f"**Operador:** {ir.entity_value}{setor_info}  \n"
                f"**Período:** {periodo.strip() or 'geral'}  \n"
                f"**Total:** {_fmt_kg(float(total))}"
            )

        # ── Produção / movimentação por operador específico ───────────────────
        if ir.intent == "producao_por_operador":
            if not ir.entity_value:
                return (
                    "Não consegui identificar o operador. "
                    "Informe o nome (ex: *john.moraes* ou só *'John'*) "
                    "ou pergunte como *'minha produção'* se for sobre você mesmo."
                )
            setor_op   = get_setor_de(ir.entity_value)
            setor_info = f" ({get_label_setor(setor_op)})" if setor_op else ""
            total = self.sql.get_producao_por_operador(ir.entity_value, ini, fim, origem)
            if float(total) == 0:
                return (
                    f"Nenhum registro encontrado para **{ir.entity_value}**{setor_info}{periodo}{orig_lbl}.\n"
                    "Verifique o nome ou o período informado."
                )
            titulo  = "Bobinas liberadas — Expedição" if setor_op == "expedicao" else "Produção"
            metrica = "Total movimentado" if setor_op == "expedicao" else "Total"
            return (
                f"### {titulo}\n\n"
                f"**Operador:** {ir.entity_value}{setor_info}  \n"
                f"**Período:** {periodo.strip() or 'geral'}  \n"
                f"**{metrica}:** {_fmt_kg(float(total))}"
            )

        # ── Produção por produto específico ───────────────────────────────────
        if ir.intent == "producao_por_produto":
            if not ir.entity_value:
                return "Não identifiquei o código do produto. Informe o código (ex: TD2AYBR1BOBR100)."
            total = self.sql.get_producao_por_produto(ir.entity_value, ini, fim, origem)
            if float(total) == 0:
                return f"Nenhuma produção encontrada para **{ir.entity_value}**{periodo}{orig_lbl}."
            return (
                f"### Produção por produto\n\n"
                f"**Produto:** `{ir.entity_value}`  \n"
                f"**Período:** {periodo.strip() or 'geral'}  \n"
                f"**Total:** {_fmt_kg(float(total))}"
            )

        # ── Ranking geral de produção ─────────────────────────────────────────
        if ir.intent == "ranking_producao_geral":
            rows = self.sql.get_ranking_producao_geral(
                ini, fim, top_n, origem, filtro_usuarios=filtro_usuarios,
            )
            if not rows:
                contexto = f" da {setor_label}" if setor_label else ""
                return f"Nenhum dado encontrado{contexto}{periodo}{orig_lbl}."
            contexto = f" da {setor_label}" if setor_label else ""
            header = f"### Top {top_n} — Produção{contexto}{periodo}{orig_lbl}\n\n"
            header += "| # | Operador | Total |\n|---|----------|-------|\n"
            linhas = "\n".join(
                f"| {r['posicao']}º | {r['operador']} | **{_fmt_kg(r['total_kg'])}** |"
                for r in rows
            )
            return header + linhas

        # ── Produção por turno ────────────────────────────────────────────────
        if ir.intent == "producao_por_turno":
            rows = self.sql.get_producao_por_turno(
                ini, fim, origem, filtro_usuarios=filtro_usuarios,
            )
            if not rows:
                return f"Nenhum dado de turno encontrado{periodo}{orig_lbl}."
            contexto = f" da {setor_label}" if setor_label else ""
            header = f"### Produção por turno{contexto}{periodo}{orig_lbl}\n\n"
            header += "| Turno | Total | Registros |\n|-------|-------|-----------|\n"
            linhas = "\n".join(
                f"| {r['turno']} | **{_fmt_kg(r['total_kg'])}** | {r['registros']} |"
                for r in rows
            )
            return header + linhas

        # ── Total geral da fábrica ────────────────────────────────────────────
        if ir.intent == "total_fabrica":
            total    = self.sql.get_total_fabrica(ini, fim, origem, filtro_usuarios)
            total_ld = self.sql.get_total_ld_fabrica(ini, fim, origem, filtro_usuarios)
            if float(total) == 0:
                return f"Nenhum dado de produção encontrado{periodo}{orig_lbl}."
            pct_ld = (float(total_ld) / float(total) * 100) if float(total) > 0 else 0
            return (
                f"### Produção total da fábrica{periodo}{orig_lbl}\n\n"
                f"| Métrica | Valor |\n|---------|-------|\n"
                f"| Total geral | **{_fmt_kg(float(total))}** |\n"
                f"| Total de LD | **{_fmt_kg(float(total_ld))}** ({pct_ld:.1f}%) |"
            )

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
