"""
orchestrator.py — Orquestrador principal do ViniAI.

Coordena o fluxo completo de processamento de uma mensagem:

  1. Lê o histórico de conversa (context_manager)
  2. Interpreta a intenção da mensagem (interpreter)
  3. Verifica se o usuário tem permissão para aquela consulta (permissions)
     → Se não tiver: retorna mensagem formal de LGPD
  4. Roteia para o handler correto:
     → smalltalk / clarify  : ChatGPT (llm_handler) responde naturalmente
     → sql                  : SQLService executa a query e formata o resultado

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

from app.agents import get_agent
from app.config import (
    OPERADORES_ATIVOS, ORIGENS,
    get_label_setor, get_operadores_setor, get_setor_de,
)
from app.context_manager import PostgresContextManager
from app.interpreter import InterpretationResult, RuleBasedInterpreter
from app.llm_handler import LLMHandler
from app.permissions import MENSAGEM_LGPD, verificar_permissao
from app.schemas import ChatProcessRequest, ChatProcessResponse
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
        recent = self.context.get_recent(payload.session_id, limit=6)

        # 2. Interpreta a intenção da mensagem
        ir = self.interpreter.interpret(payload.message)

        # 3. Verifica permissão LGPD: o perfil do usuário tem acesso a este agente?
        if not verificar_permissao(payload.user_setor, self.agent_id, ir.intent):
            self.context.append_assistant_message(payload.session_id, MENSAGEM_LGPD)
            return self._ok(MENSAGEM_LGPD, ir)

        # ── 4a. Capacidades do agente ("o que você faz?") ─────────────────────
        # Resposta estruturada com hints de uso — vinda do agents.py
        if ir.intent == "tipos_informacao":
            answer = self.capabilities or (
                f"Sou a **{self.agent_name}** e posso responder consultas do meu domínio. "
                "Tente perguntar sobre produção, LD, rankings ou turnos."
            )
            self.context.append_assistant_message(payload.session_id, answer)
            return self._ok(answer, ir)

        # ── 4b. Conversa natural → ChatGPT ───────────────────────────────────
        # Saudações, perguntas gerais, clarificações e mensagens não identificadas
        if ir.route in ("smalltalk", "clarify"):
            answer = self.llm.respond(
                message=payload.message,
                history=recent,
                intent=ir.intent,
            )
            self.context.append_assistant_message(payload.session_id, answer)
            requires_clarification = ir.route == "clarify"
            return self._ok(answer, ir, requires_clarification=requires_clarification)

        # ── 4c. Consulta ao banco de dados → SQL ──────────────────────────────
        answer = self._handle_sql(ir)
        self.context.append_assistant_message(payload.session_id, answer)
        return ChatProcessResponse(
            status="ok",
            answer=answer,
            route=ir.route,
            confidence=ir.confidence,
            used_sql=True,
            debug={
                "agent":       self.agent_name,
                "intent":      ir.intent,
                "metric":      ir.metric,
                "entity_type": ir.entity_type,
                "entity_value":ir.entity_value,
                "period_text": ir.period_text,
                "data_inicio": ir.data_inicio,
                "data_fim":    ir.data_fim,
                "top_n":       ir.top_n,
                "setor":       ir.setor,
                "origem":      ir.origem,
                "history_size":len(recent),
                "reasoning":   ir.reasoning,
                "user_setor":  payload.user_setor,
            },
        )

    # ── Handler SQL ───────────────────────────────────────────────────────────

    def _handle_sql(self, ir: InterpretationResult) -> str:
        try:
            return self._dispatch(ir)
        except Exception as exc:
            return f"Ocorreu um erro ao consultar o banco de dados: {exc}"

    def _dispatch(self, ir: InterpretationResult) -> str:
        """Despacha o intent para a query SQL correspondente e formata a resposta."""

        periodo  = _periodo_label(ir)
        orig_lbl = _origem_label(ir.origem)
        ini      = ir.data_inicio or "01/01/2025"
        fim      = ir.data_fim    or "31/12/2026"
        top_n    = ir.top_n       or 5
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
            return f"### Períodos com dados disponíveis\n\n" + "\n".join(linhas) + nota

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
                return "Não identifiquei o operador. Informe o nome (ex: ezequiel.nunes ou só 'Ezequiel')."
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
                return "Não identifiquei o operador. Informe o nome (ex: john.moraes ou só 'John')."
            setor_op   = get_setor_de(ir.entity_value)
            setor_info = f" ({get_label_setor(setor_op)})" if setor_op else ""
            total = self.sql.get_producao_por_operador(ir.entity_value, ini, fim, origem)
            if float(total) == 0:
                return (
                    f"Nenhum registro encontrado para **{ir.entity_value}**{setor_info}{periodo}{orig_lbl}.\n"
                    "Verifique o nome ou o período informado."
                )
            # Expedição recebe label diferente (movimentação, não produção)
            titulo = "Bobinas liberadas — Expedição" if setor_op == "expedicao" else "Produção"
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
