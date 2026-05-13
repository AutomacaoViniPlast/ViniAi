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

import logging
import re

logger = logging.getLogger(__name__)

from app.agents import get_agent
from app.config import (
    OPERADORES_ATIVOS, OPERADORES_EXTRUSORA, OPERADORES_REVISAO, ORIGENS,
    get_label_setor, get_operadores_setor, get_setor_de, todos_operadores,
)
from app.context_manager import PostgresContextManager
from app.interpreter import InterpretationResult, RuleBasedInterpreter, _periodo_from_text
from app.llm_handler import LLMHandler
from app.permissions import MENSAGEM_LGPD, verificar_permissao
from app.schemas import ChatProcessRequest, ChatProcessResponse, ConversationTurn
from app.sql_service_apont_rev import SQLServiceApontRev

# Logins que aparecem em STG_APONT_REV_GERAL mas são gestores, não operadores.
_GESTORES_REVISAO = {"lucas.lima", "camila.motta"}
from app.sql_service_kardex import SQLServiceKardex
from app.sql_service_sh6 import SQLServiceSH6, traduzir_recurso, traduzir_filial


# ── Helpers de formatação ─────────────────────────────────────────────────────

def _fmt_kg(valor: float) -> str:
    """Formata um valor float para exibição em KG no padrão brasileiro."""
    return f"{valor:,.2f} KG".replace(",", "X").replace(".", ",").replace("X", ".")

def _fmt_metros(valor: float) -> str:
    return f"{valor:,.2f} m".replace(",", "X").replace(".", ",").replace("X", ".")

def _fmt_numero(valor: float, casas: int = 2) -> str:
    """Formata número no padrão brasileiro sem unidade (usado em KGH, m/min, horas)."""
    fmt = f"{valor:,.{casas}f}"
    return fmt.replace(",", "X").replace(".", ",").replace("X", ".")


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


def _nome_mes_curto(mes: int) -> str:
    nomes = {
        1: "jan", 2: "fev", 3: "mar", 4: "abr", 5: "mai", 6: "jun",
        7: "jul", 8: "ago", 9: "set", 10: "out", 11: "nov", 12: "dez",
    }
    return nomes.get(mes, str(mes))


def _nome_mes_extenso(mes: int) -> str:
    nomes = {
        1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
        7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
    }
    return nomes.get(mes, str(mes))


def _fmt_periodos_disponiveis(periodos: list[dict]) -> str:
    """Formata anos/meses disponíveis agrupados por ano."""
    if not periodos:
        return "_Nenhum período encontrado._"
    linhas = []
    for bloco in periodos:
        meses = ", ".join(_nome_mes_curto(m) for m in bloco["meses"])
        linhas.append(f"- **{bloco['ano']}**: {meses}")
    return "\n".join(linhas)


def _extremos_periodos(periodos: list[dict]) -> tuple[str | None, str | None]:
    """Retorna o primeiro e o último mês disponível em formato legível."""
    if not periodos:
        return None, None
    primeiro_ano = periodos[0]["ano"]
    primeiro_mes = periodos[0]["meses"][0]
    ultimo_ano = periodos[-1]["ano"]
    ultimo_mes = periodos[-1]["meses"][-1]
    return (
        f"{_nome_mes_extenso(primeiro_mes)} de {primeiro_ano}",
        f"{_nome_mes_extenso(ultimo_mes)} de {ultimo_ano}",
    )


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
        self.apont_rev    = SQLServiceApontRev()
        self.llm          = LLMHandler(
            agent_name=agent["name"],
            system_prompt=agent["system_prompt"],
        )

    # ── Ponto de entrada ──────────────────────────────────────────────────────

    def process(self, payload: ChatProcessRequest) -> ChatProcessResponse:
        """Processa uma mensagem e retorna a resposta do agente."""

        is_whatsapp = payload.channel == "whatsapp"
        # session_id usado para persistência de intents — None para WhatsApp,
        # pois esse canal não usa o PostgreSQL N8N.
        sid = None if is_whatsapp else payload.session_id

        # 1. Lê o histórico para passar ao LLM como contexto.
        #    WhatsApp usa session_id = número de telefone (não existe na tabela mensagens),
        #    então pula o lookup do PostgreSQL para evitar queries desnecessárias e
        #    esgotamento do pool de conexões em caso de retentativas do N8N.
        if is_whatsapp:
            recent, history_failed = [], False
        else:
            self.context.append_user_message(payload.session_id, payload.message)
            recent, history_failed = self.context.get_recent(payload.session_id, limit=32)

        # 2. Resolve campos do usuário — topo do payload tem prioridade;
        #    fallback para metadata (compatibilidade com N8N que envia via metadata)
        user_name  = payload.user_name  or payload.metadata.get("userName") or payload.metadata.get("user_name")
        user_setor = payload.user_setor or payload.metadata.get("setor")    or payload.metadata.get("user_setor")
        user_cargo = payload.user_cargo or payload.metadata.get("cargo")    or payload.metadata.get("user_cargo")

        # 3. Normaliza a mensagem (corrige typos/abreviações) antes da classificação por regex
        normalized_message = self.llm.normalize_message(payload.message)

        # 4. Interpreta a intenção da mensagem normalizada
        ir = self.interpreter.interpret(normalized_message)

        # 5. Verifica permissão LGPD
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
        # Extrai período explícito da mensagem normalizada (None se não mencionado)
        msg_ini, msg_fim, msg_lbl = _periodo_from_text(normalized_message)
        periodo_explicito = bool(msg_ini or msg_fim)

        # Caso 1: mensagem ambígua com período novo → herda intent do histórico
        # Ex: "Quero saber de janeiro!" após consulta de LD
        # Se a mensagem também pedir metros (ex: "LD em metros de janeiro"), força MT.
        rag_attempted = False
        if ir.route in ("clarify", "smalltalk") and ir.confidence < 0.75 and periodo_explicito:
            rag_attempted = True
            followup_ir = self._try_context_followup(recent, msg_ini, msg_fim, msg_lbl, session_id=sid)
            if followup_ir:
                if self.interpreter._METROS_UNIDADE.search(normalized_message):
                    followup_ir.unidade_filtro = "MT"
                ir = followup_ir
                logger.debug("[%s] RAG carry-over: intent '%s' com novo período.", self.agent_name, ir.intent)

        # Caso 4: mensagem ambígua sem período mas com recurso → herda intent + período do histórico
        # Ex: "E da MAC2?" após "Produção da MAC1 e 2 ontem?" — sem período, mas menciona recurso
        # Sem este caso, o LLM responde com valor inventado baseado no histórico (alucinação)
        # Caso 4b: sem período e sem recurso, mas pedindo metros lineares → herda intent + período + força MT
        # Ex: "Quantos metros lineares no total?" após "Total de LD em abril de 2026"
        elif ir.route in ("clarify", "smalltalk") and ir.confidence < 0.75 and not periodo_explicito:
            rag_attempted = True
            recurso_novo = self.interpreter._extract_recurso(normalized_message)
            if recurso_novo:
                followup_ir = self._try_context_followup(recent, None, None, None, recursos_new=recurso_novo, session_id=sid)
                if followup_ir:
                    ir = followup_ir
                    logger.debug("[%s] RAG recurso-carry (clarify): intent '%s' com recurso %s.", self.agent_name, ir.intent, recurso_novo)
            elif self.interpreter._METROS_UNIDADE.search(normalized_message):
                followup_ir = self._try_context_followup(recent, None, None, None, session_id=sid)
                if followup_ir:
                    followup_ir.unidade_filtro = "MT"
                    ir = followup_ir
                    logger.debug("[%s] MT carry-over: intent '%s' com unidade_filtro=MT.", self.agent_name, ir.intent)

        # Caso 3: SQL genérico sem operador → follow-up de recurso/extrusora
        # Ex: "E na extrusora 2?" após consulta de KGH herda intent kgh + atualiza recurso
        elif (
            ir.route == "sql"
            and ir.intent == "producao_por_operador"
            and not ir.entity_value
            and ir.confidence < 0.75
        ):
            rag_attempted = True
            followup_ir = self._try_context_followup(
                recent, msg_ini, msg_fim, msg_lbl, recursos_new=ir.recursos, session_id=sid,
            )
            if followup_ir:
                ir = followup_ir
                logger.debug("[%s] RAG recurso-carry: intent '%s' com novo recurso.", self.agent_name, ir.intent)

        # Caso 2: consulta SQL sem período explícito → herda período do histórico
        # Ex: "E o do Igor?" após "Qual o LD do Ezequiel em janeiro?" herda janeiro
        # Também ativa para mensagens curtas (≤ 5 palavras) mesmo com alta confiança —
        # evita que "E da extrusora 1?" use período padrão ao invés de herdar "ontem"
        elif ir.route == "sql" and not periodo_explicito and (
            ir.confidence < 0.87 or len(payload.message.strip().split()) <= 5
        ):
            rag_attempted = True
            inherited = self._inherit_period_from_history(recent, session_id=sid)
            if inherited:
                ir.data_inicio, ir.data_fim, ir.period_text = inherited
                logger.debug(
                    "[%s] period-inherit: '%s' herdado do histórico (conf=%.2f).",
                    self.agent_name, inherited[2], ir.confidence,
                )

        # ── 4c. Expedição — resposta fixa (funcionalidade não implementada) ────
        if ir.intent == "expedicao_nao_implementada":
            answer = (
                "Ainda não desenvolvemos nenhuma função que aborde a Expedição. "
                "Entre em contato com o departamento de Tecnologia e Inovação."
            )
            self.context.append_assistant_message(payload.session_id, answer)
            return self._ok(answer, ir)

        # ── 4d. Conversação natural → LLM ────────────────────────────────────
        if ir.route in ("smalltalk", "clarify"):
            user_context = {"name": user_name, "setor": user_setor, "cargo": user_cargo}
            logger.debug("[%s] user_context recebido: %s", self.agent_name, user_context)
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
            resp.debug["normalized_message"] = normalized_message if normalized_message != payload.message else None
            return resp

        # ── 4e. Auto-inject: quando intent é de operador mas nenhum foi ───────
        #        extraído do texto, usa o próprio usuário autenticado.
        #        Só injeta se o setor do usuário bate com o intent.
        if (
            ir.intent in ("geracao_ld_por_operador", "producao_por_operador", "resumo_qualidade")
            and not ir.entity_value
        ):
            user_login = _user_login_from_name(user_name)
            if user_login:
                setor_usuario = get_setor_de(user_login)
                if ir.intent in ("geracao_ld_por_operador", "resumo_qualidade") and setor_usuario == "revisao":
                    ir.entity_value = user_login
                    logger.debug("[%s] Auto-inject (revisao): entity_value='%s'.", self.agent_name, user_login)
                elif ir.intent == "producao_por_operador" and setor_usuario == "extrusora":
                    ir.entity_value = user_login
                    logger.debug("[%s] Auto-inject (extrusora): entity_value='%s'.", self.agent_name, user_login)

        # ── 4e. Consulta ao banco de dados → SQL ─────────────────────────────
        answer = self._handle_sql(ir)
        if history_failed and rag_attempted:
            answer += (
                "\n\n_Não consegui acessar o histórico desta conversa — "
                "se sua pergunta depende de algo que perguntou antes, repita o contexto._"
            )
        self.context.append_assistant_message(payload.session_id, answer)
        # Persiste o intent resolvido para carry-over preciso nas próximas mensagens.
        # WhatsApp (sid=None) é ignorado pois não usa o PostgreSQL N8N.
        if sid:
            self.context.save_intent(sid, ir)
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
                "history_size":       len(recent),
                "reasoning":          ir.reasoning,
                "user_setor":         user_setor,
                "user_name":          user_name,
                "periodo_explicito":  periodo_explicito,
                "normalized_message": normalized_message if normalized_message != payload.message else None,
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
        session_id: str | None = None,
    ) -> InterpretationResult | None:
        """
        RAG conversacional: quando a mensagem atual só especifica um período
        sem intent claro, reutiliza o intent SQL da última consulta executada.

        Estratégia (em ordem de prioridade):
          1. Extrai operador de mensagens curtas recentes (clarificações como "Ezequiel").
          2. Busca o intent salvo no banco (preciso — exatamente o que foi executado).
          3. Fallback: re-interpreta as mensagens de texto do histórico (comportamento legado).
          4. Aplica sobreposições: entidade clarificada + período novo + recurso novo.

        Exemplo:
          Histórico: ["Qual foi o LD nesse mês?", "Ezequiel", "Quero saber desse mês!"]
          Resultado: intent=geracao_ld_por_operador, entity=ezequiel.nunes, período=atual
        """
        user_msgs = [t.content for t in reversed(recent) if t.role == "user"]

        # Passo 1: extrai operador de mensagens curtas (clarificações de nome)
        entity_override: str | None = None
        for msg in user_msgs:
            if len(msg.strip().split()) <= 3:
                op = self.interpreter._extract_operator(msg)
                if op:
                    entity_override = op
                    break

        def _apply_overrides(base_ir: InterpretationResult) -> InterpretationResult:
            if entity_override and not base_ir.entity_value:
                base_ir.entity_value = entity_override
            if ini_new:
                base_ir.data_inicio = ini_new
            if fim_new:
                base_ir.data_fim = fim_new
            if lbl_new:
                base_ir.period_text = lbl_new
            if recursos_new:
                base_ir.recursos = recursos_new
            base_ir.route = "sql"
            return base_ir

        # Passo 2: usa o intent salvo no banco (preciso — sem re-interpretação de texto)
        if session_id:
            stored_ir = self.context.get_last_intent(session_id)
            if stored_ir and stored_ir.route == "sql":
                stored_ir.reasoning = f"[db-carry] {stored_ir.reasoning or ''}"
                return _apply_overrides(stored_ir)

        # Passo 3: fallback — re-interpreta as mensagens de texto do histórico
        for msg in user_msgs:
            if len(msg.strip().split()) <= 3:
                continue  # pula clarificações curtas

            prev_ir = self.interpreter.interpret(msg)
            if prev_ir.route == "sql" and prev_ir.confidence >= 0.55:
                prev_ir.reasoning = f"[text-carry] {prev_ir.reasoning}"
                return _apply_overrides(prev_ir)

        return None

    # ── Herança de Período ────────────────────────────────────────────────────

    def _inherit_period_from_history(
        self,
        recent: list[ConversationTurn],
        max_lookback: int = 6,
        session_id: str | None = None,
    ) -> tuple[str, str, str] | None:
        """
        Herda o período da última consulta SQL executada.

        Usado quando a mensagem atual é uma consulta SQL clara mas sem período
        especificado — ex: "E o do Igor?" após "Qual o LD do Ezequiel em janeiro?".
        Nesse caso, herda 'janeiro' em vez de usar o período padrão (mês atual).

        Prioridade:
          1. Período do intent salvo no banco (preciso — o que foi realmente executado).
          2. Fallback: escaneia texto das mensagens recentes (comportamento legado).

        Parâmetros:
          recent       : histórico recente (ConversationTurn)
          max_lookback : limita quantas mensagens atrás pesquisar no fallback (padrão: 6)
          session_id   : ID da sessão para buscar no banco; None pula o banco

        Retorna (data_inicio, data_fim, period_text) ou None se não encontrar.
        """
        # Passo 1: usa o período do intent salvo no banco (preciso)
        if session_id:
            stored_ir = self.context.get_last_intent(session_id)
            if stored_ir and stored_ir.data_inicio and stored_ir.data_fim:
                return stored_ir.data_inicio, stored_ir.data_fim, stored_ir.period_text or ""

        # Passo 2: fallback — escaneia o texto das mensagens recentes
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
        top_n     = ir.top_n or 10
        recursos  = ir.recursos  # None = ambas extrusoras (default no service)
        is_diaria = self._is_diaria(ir)
        rec_lbl   = self._recurso_label(recursos)

        # ── Perda de material (LD + BAG) ──────────────────────────────────────
        if ir.intent == "perda_material":
            resumo = self.kardex.get_resumo_qualidade(
                ini, fim,
                operador=ir.entity_value or None,
                origem=ir.origem,
                filtro_usuarios=OPERADORES_REVISAO if not ir.entity_value else None,
            )
            ld_kg      = float(resumo["Y"]["KG"])
            bag_kg     = float(resumo["BAG"]["KG"])
            inteiro_kg = float(resumo["I"]["KG"])
            fp_kg      = float(resumo["P"]["KG"])
            perda      = ld_kg + bag_kg
            total_insp = inteiro_kg + ld_kg + fp_kg + bag_kg

            if total_insp == 0:
                return f"🔍 Nenhum dado de qualidade encontrado{periodo}."

            pct   = (perda / total_insp) * 100
            tipo  = "dia" if is_diaria else "mês"
            nome  = f" — {ir.entity_value}" if ir.entity_value else ""
            header = (
                f"🗑️ **Perda de material{nome}**\n"
                f"📅 Período ({tipo}){periodo}\n\n"
                "| Tipo | Total |\n|------|-------|\n"
            )
            linhas = []
            if ld_kg > 0:
                linhas.append(f"| ⚠️ LD (defeito) | **{_fmt_kg(ld_kg)}** |")
            if bag_kg > 0:
                linhas.append(f"| 🛍️ BAG | **{_fmt_kg(bag_kg)}** |")
            linhas.append(f"| **🗑️ Total Perda** | **{_fmt_kg(perda)}** |")
            rodape = (
                f"\n\n📦 Total inspecionado: {_fmt_kg(total_insp)}\n"
                f"📊 Taxa de perda: **{pct:.1f}%**"
            )
            return header + "\n".join(linhas) + rodape

        # ── Comparação entre dois períodos ────────────────────────────────────
        if ir.intent == "comparacao_periodos":
            return self._handle_comparacao_periodos(ir)

        # ── Ranking de revisão (STG_APONT_REV_GERAL) ─────────────────────────
        if ir.intent == "ranking_revisao":
            def _label_op_rev(login: str) -> str:
                sufixo = " (Gestor)" if login.lower() in _GESTORES_REVISAO else ""
                return f"{login}{sufixo}"

            if ir.entity_value:
                # Operador específico → total individual
                dados = self.apont_rev.get_revisao_por_operador(ir.entity_value, ini, fim)
                if dados["total_metros"] == 0:
                    return f"🔍 Nenhum apontamento de revisão encontrado para **{_label_op_rev(ir.entity_value)}**{periodo}."
                return (
                    f"📋 **Revisão — {_label_op_rev(ir.entity_value)}**{periodo}\n\n"
                    f"| Métrica | Valor |\n|---------|-------|\n"
                    f"| 📏 Total revisado | **{_fmt_metros(dados['total_metros'])}** |\n"
                    f"| 📦 Bobinas | {dados['total_bobinas']} |"
                )
            # Sem operador → ranking
            rows = self.apont_rev.get_ranking_revisao(ini, fim, top_n, operadores=OPERADORES_REVISAO)
            if not rows:
                return f"🔍 Nenhum apontamento de revisão encontrado{periodo}."
            header = f"🏆 **Top {top_n} — Revisão (metros revisados)**{periodo}\n\n"
            header += "| # | Operador | Total (m) | Bobinas |\n|---|----------|-----------|--------|\n"
            linhas = "\n".join(
                f"| {_posicao_label(r['posicao'])} | {_label_op_rev(r['operador'])} | **{_fmt_metros(r['total_metros'])}** | {r['registros']} |"
                for r in rows
            )
            return header + linhas

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
        if ir.intent == "producao_por_dia":
            rows = self.sql.get_producao_por_dia(ini, fim, recursos=recursos)
            if not rows:
                return f"🔍 Nenhum dado de produção encontrado{periodo}{rec_lbl}."
            total_periodo = sum(r["total_kg"] for r in rows)
            header = f"📅 **Produção dia a dia da fábrica**{periodo}{rec_lbl}\n\n"
            header += "| Data | Total KG | Registros |\n|------|----------|-----------|\n"
            linhas = "\n".join(
                f"| {r['data']} | **{_fmt_kg(r['total_kg'])}** | {r['registros']} |"
                for r in rows
            )
            resumo = f"\n\n**Total do período:** {_fmt_kg(total_periodo)}"
            return header + linhas + resumo

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

        # ── Ranking de produção por operador (V_APONT_REV_GERAL) ────────────────
        if ir.intent == "ranking_producao_geral":
            rows = self.apont_rev.get_ranking_producao_extrusora(ini, fim, top_n)
            if not rows:
                return f"🔍 Nenhum dado encontrado{periodo}."
            header = f"🏆 **Top {top_n} — Produção**{periodo}\n\n"
            header += "| # | Operador | Total (m) |\n|---|----------|-----------|\n"
            linhas = "\n".join(
                f"| {_posicao_label(r['posicao'])} | {r['operador']} | **{_fmt_metros(r['total_metros'])}** |"
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
                f"| {r['recurso_label']} | **{_fmt_numero(r['horas'])} h** | {_fmt_numero(r['minutos'], 0)} min |"
                for r in rows
            )
            return header + linhas

        # ── Produção por operador específico (SH6) ────────────────────────────
        if ir.intent == "producao_por_operador":
            if not ir.entity_value:
                # Nenhum operador mencionado → retorna total geral da fábrica para o período
                total = self.sql.get_producao_total(ini, fim, recursos=recursos, is_diaria=is_diaria)
                if float(total) == 0:
                    return f"🔍 Nenhum dado de produção encontrado{periodo}{rec_lbl}."
                tipo = "dia" if is_diaria else "mês"
                return (
                    f"🏭 **Produção total da fábrica — {tipo}**{periodo}{rec_lbl}\n\n"
                    f"| Métrica | Valor |\n|---------|-------|\n"
                    f"| ⚙️ Total geral | **{_fmt_kg(float(total))}** |"
                )

            # Operador da revisão → dados estão no KARDEX (qualidade), não no SH6
            if ir.entity_value in OPERADORES_REVISAO:
                resumo = self.kardex.get_resumo_qualidade(ini, fim, operador=ir.entity_value, origem=ir.origem)
                inteiro_kg = float(resumo["I"]["KG"])
                ld_kg      = float(resumo["Y"]["KG"])
                ld_mt      = float(resumo["Y"]["MT"])
                fp_kg      = float(resumo["P"]["KG"])
                fp_mt      = float(resumo["P"]["MT"])
                bag_kg     = float(resumo["BAG"]["KG"])
                total_kg   = inteiro_kg + ld_kg + fp_kg + bag_kg
                if total_kg == 0 and ld_mt == 0 and fp_mt == 0:
                    return f"🔍 Nenhum registro encontrado para **{ir.entity_value}**{periodo}."
                tipo   = "dia" if is_diaria else "mês"
                header = (
                    f"⚠️ **Revisão por qualidade — {ir.entity_value}**\n"
                    f"📅 Período ({tipo}){periodo}\n\n"
                    "| Qualidade | Total |\n|-----------|-------|\n"
                )
                linhas = []
                if inteiro_kg > 0:
                    linhas.append(f"| ✅ Inteiro | **{_fmt_kg(inteiro_kg)}** |")
                if ld_kg > 0:
                    linhas.append(f"| ⚠️ LD | **{_fmt_kg(ld_kg)}** |")
                if ld_mt > 0:
                    linhas.append(f"| ⚠️ LD | **{_fmt_metros(ld_mt)}** |")
                if fp_kg > 0:
                    linhas.append(f"| 🔶 Fora de Padrão | **{_fmt_kg(fp_kg)}** |")
                if fp_mt > 0:
                    linhas.append(f"| 🔶 Fora de Padrão | **{_fmt_metros(fp_mt)}** |")
                if bag_kg > 0:
                    linhas.append(f"| 🛍️ BAG | **{_fmt_kg(bag_kg)}** |")
                if total_kg > 0:
                    linhas.append(f"| **📦 Total** | **{_fmt_kg(total_kg)}** |")
                return header + "\n".join(linhas)

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
            if ir.entity_type == "extrusora":
                rows = self.sql.get_metros_por_minuto_por_recurso(ini, fim, recursos=recursos, is_diaria=is_diaria)
                if not rows:
                    return f"🔍 Nenhum dado de metros/min encontrado{periodo}{rec_lbl}."
                blocos = []
                for r in rows:
                    blocos.append(
                        f"**{r['recurso_label']}**\n\n"
                        f"| Métrica | Valor |\n|---------|-------|\n"
                        f"| Metros totais | {_fmt_metros(r['metros'])} |\n"
                        f"| Minutos totais | {_fmt_numero(r['minutos'], 0)} min |\n"
                        f"| **Média m/min** | **{_fmt_numero(r['resultado'], 4)}** |"
                    )
                header = f"📏 **Metros por minuto por extrusora**{periodo}{rec_lbl}\n\n"
                return header + "\n\n".join(blocos)
            data = self.sql.get_metros_por_minuto(ini, fim, recursos=recursos, is_diaria=is_diaria)
            if data["resultado"] == 0:
                return f"🔍 Nenhum dado de metros/min encontrado{periodo}{rec_lbl}."
            return (
                f"📏 **Metros por minuto**{periodo}{rec_lbl}\n\n"
                f"| Métrica | Valor |\n|---------|-------|\n"
                f"| Metros totais | {_fmt_metros(data['metros'])} |\n"
                f"| Minutos totais | {_fmt_numero(data['minutos'], 0)} min |\n"
                f"| **Média m/min** | **{_fmt_numero(data['resultado'], 4)}** |"
            )

        # ── Produção por turno (KARDEX) ──────────────────────────────────────────
        # PENDÊNCIA: alguns turnos retornam valores negativos no KARDEX. Investigar
        # origem dos registros com QTDPROD negativo antes de exibir ao usuário.
        if ir.intent == "producao_por_turno":
            rows = self.kardex.get_producao_por_turno(ini, fim, recursos=recursos)
            if not rows:
                return f"🔍 Nenhum dado por turno encontrado{periodo}{rec_lbl}."
            por_turno: dict[str, dict] = {}
            for r in rows:
                t = r["turno"] or "—"
                if t not in por_turno:
                    por_turno[t] = {"KG": 0.0, "MT": 0.0, "registros": 0}
                um = (r["unidade"] or "").upper()
                if um == "KG":
                    por_turno[t]["KG"] += r["total"]
                elif um == "MT":
                    por_turno[t]["MT"] += r["total"]
                por_turno[t]["registros"] += r["registros"]
            header = f"🔄 **Produção por turno**{periodo}{rec_lbl}\n\n"
            header += "| Turno | Total KG | Registros |\n|-------|----------|----------|\n"
            linhas = [
                f"| {turno} | **{_fmt_kg(dados['KG'])}** | {dados['registros']} |"
                for turno, dados in sorted(por_turno.items())
            ]
            return header + "\n".join(linhas)

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
                    f"| KG total | {_fmt_kg(r['total_kg'])} |\n"
                    f"| Horas totais | {_fmt_numero(r['horas'])} h |\n"
                    f"| **KGH** | **{_fmt_numero(r['kgh'])}** |"
                )
                blocos.append(bloco)
            header = f"⚡ **KG/hora por extrusora**{periodo}{rec_lbl}\n\n"
            return header + "\n\n".join(blocos)

        # ── KGH + metros por minuto combinados (SH6) ─────────────────────────
        if ir.intent == "kgh_e_metros_por_minuto":
            kgh_rows = self.sql.get_kgh(ini, fim, recursos=recursos, is_diaria=is_diaria)
            mmin_data = self.sql.get_metros_por_minuto(ini, fim, recursos=recursos, is_diaria=is_diaria)
            partes = []
            if kgh_rows:
                blocos_kgh = []
                for r in kgh_rows:
                    blocos_kgh.append(
                        f"**{r['recurso_label']}**\n\n"
                        f"| Métrica | Valor |\n|---------|-------|\n"
                        f"| KG total | {_fmt_kg(r['total_kg'])} |\n"
                        f"| Horas totais | {_fmt_numero(r['horas'])} h |\n"
                        f"| **KGH** | **{_fmt_numero(r['kgh'])}** |"
                    )
                partes.append(f"⚡ **KG/hora por extrusora**{periodo}{rec_lbl}\n\n" + "\n\n".join(blocos_kgh))
            if mmin_data and mmin_data["resultado"] != 0:
                partes.append(
                    f"📏 **Metros por minuto**{periodo}{rec_lbl}\n\n"
                    f"| Métrica | Valor |\n|---------|-------|\n"
                    f"| Metros totais | {_fmt_metros(mmin_data['metros'])} |\n"
                    f"| Minutos totais | {_fmt_numero(mmin_data['minutos'], 0)} min |\n"
                    f"| **Média m/min** | **{_fmt_numero(mmin_data['resultado'], 4)}** |"
                )
            if not partes:
                return f"🔍 Nenhum dado encontrado{periodo}{rec_lbl}."
            return "\n\n---\n\n".join(partes)

        # ── Intents KARDEX — consultas que envolvem qualidade do material ────────

        # ── Qualidade da produção: Inteiro / LD / FP (KARDEX) ───────────────────
        # Exibe breakdown completo: total geral + Inteiro (sem defeito) + LD (defeito) + FP
        if ir.intent == "periodos_disponiveis":
            periodos_sh6 = self.sql.get_periodos_disponiveis(recursos=recursos)
            periodos_kardex = self.kardex.get_periodos_disponiveis()
            periodos_revisao = self.apont_rev.get_periodos_disponiveis()
            if not periodos_sh6 and not periodos_kardex and not periodos_revisao:
                return "🔍 Não encontrei períodos disponíveis nas bases consultadas."

            if ir.metric == "producao":
                if not periodos_sh6:
                    return "🔍 Não encontrei períodos disponíveis para produção na base SH6."
                ini_sh6, fim_sh6 = _extremos_periodos(periodos_sh6)
                return (
                    "🗓️ **Tenho estes períodos disponíveis para produção (SH6):**\n\n"
                    f"Cobertura: **{ini_sh6}** até **{fim_sh6}**\n\n"
                    f"{_fmt_periodos_disponiveis(periodos_sh6)}"
                )

            if ir.metric == "qualidade":
                if not periodos_kardex:
                    return "🔍 Não encontrei períodos disponíveis para qualidade na base KARDEX."
                ini_kx, fim_kx = _extremos_periodos(periodos_kardex)
                return (
                    "🗓️ **Tenho estes períodos disponíveis para qualidade (KARDEX):**\n\n"
                    f"Cobertura: **{ini_kx}** até **{fim_kx}**\n\n"
                    f"{_fmt_periodos_disponiveis(periodos_kardex)}"
                )

            if ir.metric == "revisao":
                if not periodos_revisao:
                    return "🔍 Não encontrei períodos disponíveis para revisão na base V_APONT_REV_GERAL."
                ini_rev, fim_rev = _extremos_periodos(periodos_revisao)
                return (
                    "🗓️ **Tenho estes períodos disponíveis para revisão (V_APONT_REV_GERAL):**\n\n"
                    f"Cobertura: **{ini_rev}** até **{fim_rev}**\n\n"
                    f"{_fmt_periodos_disponiveis(periodos_revisao)}"
                )

            partes = ["🗓️ **Tenho estes períodos disponíveis nas bases que eu consulto:**"]

            if periodos_sh6:
                ini_sh6, fim_sh6 = _extremos_periodos(periodos_sh6)
                partes.append(
                    "### Extrusora / Produção (SH6)\n"
                    f"Cobertura: **{ini_sh6}** até **{fim_sh6}**\n\n"
                    f"{_fmt_periodos_disponiveis(periodos_sh6)}"
                )

            if periodos_kardex:
                ini_kx, fim_kx = _extremos_periodos(periodos_kardex)
                partes.append(
                    "### Qualidade (KARDEX)\n"
                    f"Cobertura: **{ini_kx}** até **{fim_kx}**\n\n"
                    f"{_fmt_periodos_disponiveis(periodos_kardex)}"
                )

            if periodos_revisao:
                ini_rev, fim_rev = _extremos_periodos(periodos_revisao)
                partes.append(
                    "### Revisão (V_APONT_REV_GERAL)\n"
                    f"Cobertura: **{ini_rev}** até **{fim_rev}**\n\n"
                    f"{_fmt_periodos_disponiveis(periodos_revisao)}"
                )

            partes.append(
                "Se você quiser, eu também posso te responder isso focando só em "
                "**produção**, **qualidade**, **revisão**, **LD** ou **extrusora**."
            )
            return "\n\n".join(partes)

        if ir.intent == "ld_total":
            total_ld = self.kardex.get_ld_total(
                ini, fim,
                recursos=recursos,
                origem=ir.origem,
            )
            if not any(float(total_ld.get(um, 0)) > 0 for um in ("KG", "MT")):
                return f"🔍 Nenhum registro encontrado para essa solicitação{periodo}{rec_lbl}."

            if ir.unidade_filtro == "MT":
                mt_val = float(total_ld.get("MT", 0))
                if mt_val == 0:
                    kg_val = float(total_ld.get("KG", 0))
                    return (
                        f"🔍 Não há registros de LD em metros para este período{periodo}.\n\n"
                        f"O total em KG foi **{_fmt_kg(kg_val)}**."
                    )
                fmt_mt = f"{mt_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return f"⚠️ **Total de LD em metros**{periodo}{rec_lbl}\n\n**{fmt_mt} MT**"

            return (
                f"⚠️ **Total de LD**{periodo}{rec_lbl}\n\n"
                f"**{_fmt_quantidade(total_ld)}**"
            )

        if ir.intent == "geracao_ld_por_operador":
            if not ir.entity_value:
                return "Preciso do nome do operador para consultar o LD identificado."

            # Operador da extrusora não tem registros de revisão no KARDEX
            if ir.entity_value in OPERADORES_EXTRUSORA:
                return (
                    f"**{ir.entity_value}** é um operador da **Extrusora** — "
                    "não tem registros de revisão de qualidade.\n\n"
                    "Para consultar a produção dele, pergunte sobre produção."
                )

            total_ld = self.kardex.get_ld_por_operador(
                ir.entity_value,
                ini, fim,
                origem=ir.origem,
            )
            if not any(float(total_ld.get(um, 0)) > 0 for um in ("KG", "MT")):
                nome = f" para **{ir.entity_value}**" if ir.entity_value else ""
                return f"🔍 Nenhum registro encontrado para essa solicitação{nome}{periodo}."

            nome_str = f" — {ir.entity_value}" if ir.entity_value else ""

            if ir.unidade_filtro == "MT":
                mt_val = float(total_ld.get("MT", 0))
                if mt_val == 0:
                    kg_val = float(total_ld.get("KG", 0))
                    return (
                        f"🔍 Não há registros de LD em metros para **{ir.entity_value}**{periodo}.\n\n"
                        f"O total em KG foi **{_fmt_kg(kg_val)}**."
                    )
                fmt_mt = f"{mt_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                return (
                    f"⚠️ **LD em metros{nome_str}**\n"
                    f"📅 Período{periodo}\n\n"
                    f"**{fmt_mt} MT**"
                )

            return (
                f"⚠️ **LD identificado{nome_str}**\n"
                f"📅 Período{periodo}\n\n"
                f"**{_fmt_quantidade(total_ld)}**"
            )

        if ir.intent == "resumo_qualidade":
            resumo = self.kardex.get_resumo_qualidade(
                ini, fim,
                operador=ir.entity_value or None,
                origem=ir.origem,
            )
            inteiro_kg = float(resumo["I"]["KG"])
            inteiro_mt = float(resumo["I"]["MT"])
            ld_kg      = float(resumo["Y"]["KG"])
            ld_mt      = float(resumo["Y"]["MT"])
            fp_kg      = float(resumo["P"]["KG"])
            fp_mt      = float(resumo["P"]["MT"])
            bag_kg     = float(resumo["BAG"]["KG"])
            bag_mt     = float(resumo["BAG"]["MT"])
            total_kg   = inteiro_kg + ld_kg + fp_kg + bag_kg
            total_mt   = inteiro_mt + ld_mt + fp_mt + bag_mt

            if total_kg == 0 and total_mt == 0:
                nome = f" para **{ir.entity_value}**" if ir.entity_value else ""
                return f"🔍 Nenhum registro encontrado para essa solicitação{nome}{periodo}."

            def _pct_kg(v: float) -> str:
                if total_kg == 0:
                    return "—"
                return f"{v / total_kg * 100:.2f}%".replace(".", ",")

            def _pct_mt(v: float) -> str:
                if total_mt == 0:
                    return "—"
                return f"{v / total_mt * 100:.2f}%".replace(".", ",")

            def _fmt_mt(v: float) -> str:
                return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

            tipo     = "dia" if is_diaria else "mês"
            nome_str = f" — {ir.entity_value}" if ir.entity_value else ""
            filtro   = ir.qualidade_filtro  # None = todos; ["Y"] = só LD; etc.

            _DADOS: dict[str, tuple[str, float, float]] = {
                "I":   ("✅ Inteiro",        inteiro_kg, inteiro_mt),
                "Y":   ("⚠️ LD",            ld_kg,      ld_mt),
                "P":   ("🔶 Fora de Padrão", fp_kg,      fp_mt),
                "BAG": ("🛍️ BAG",           bag_kg,     bag_mt),
            }
            _ORDEM = ["I", "Y", "P", "BAG"]

            # Isolado: um único indicador pedido — formato compacto sem percentuais
            if filtro and len(filtro) == 1:
                cod = filtro[0]
                label, v_kg, v_mt = _DADOS[cod]
                return (
                    f"{label}{nome_str}\n"
                    f"📅 Período ({tipo}){periodo}\n\n"
                    f"| KG | MT |\n|----|----|\n"
                    f"| **{_fmt_kg(v_kg)}** | **{_fmt_mt(v_mt)} MT** |"
                )

            # Múltiplos ou todos: tabela completa com percentuais
            header = (
                f"⚠️ **Produção por qualidade{nome_str}**\n"
                f"📅 Período ({tipo}){periodo}\n\n"
                "| Qualidade | KG | % KG | MT | % MT |\n"
                "|-----------|----|------|----|------|\n"
            )
            mostrar = set(filtro) if filtro else set(_ORDEM)
            linhas = []
            for cod in _ORDEM:
                if cod not in mostrar:
                    continue
                label, v_kg, v_mt = _DADOS[cod]
                if v_kg > 0 or v_mt > 0:
                    mt_col = f"**{_fmt_mt(v_mt)} MT**" if v_mt > 0 else "—"
                    linhas.append(
                        f"| {label} | **{_fmt_kg(v_kg)}** | {_pct_kg(v_kg)} | {mt_col} | {_pct_mt(v_mt)} |"
                    )

            # Totais de perda e geral apenas no resumo completo
            if filtro is None:
                perda_kg = ld_kg + fp_kg + bag_kg
                perda_mt = ld_mt + fp_mt + bag_mt
                if perda_kg > 0 or perda_mt > 0:
                    perda_mt_col = f"**{_fmt_mt(perda_mt)} MT**" if perda_mt > 0 else "—"
                    linhas.append(
                        f"| **⚠️ Total perda** | **{_fmt_kg(perda_kg)}** | **{_pct_kg(perda_kg)}** | {perda_mt_col} | **{_pct_mt(perda_mt)}** |"
                    )
                if total_kg > 0 or total_mt > 0:
                    total_mt_col = f"**{_fmt_mt(total_mt)} MT**" if total_mt > 0 else "—"
                    linhas.append(
                        f"| **📦 Total geral** | **{_fmt_kg(total_kg)}** | **100%** | {total_mt_col} | **100%** |"
                    )
            return header + "\n".join(linhas)

        # ── Ranking de operadores com mais LD (KARDEX) ────────────────────────────
        if ir.intent == "ranking_usuarios_ld":
            rows = self.kardex.get_ranking_ld(
                ini, fim, limite=top_n,
                recursos=recursos,
                filtro_usuarios=OPERADORES_REVISAO,
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
                filtro_usuarios=OPERADORES_REVISAO,
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

        # ── Produção agrupada por produto (todos, sem filtro qualidade) ──────────
        if ir.intent == "producao_agrupada_por_produto":
            top_n = ir.top_n or 10
            rows = self.kardex.get_producao_por_produto(
                ini, fim, limite=top_n, origem=ir.origem,
            )
            if not rows:
                return f"🔍 Nenhum dado de produção por produto encontrado{periodo}."
            header = f"📦 **Produção por produto**{periodo}\n\n"
            header += "| # | Produto | Descrição | Total KG | Registros |\n|---|---------|-----------|----------|----------|\n"
            linhas = "\n".join(
                f"| {_posicao_label(r['posicao'])} | {r['produto']} | {r['descricao'] or '-'} "
                f"| **{_fmt_kg(r['total_kg'])}** | {r['registros']} |"
                for r in rows
            )
            return header + linhas

        # ── Produção agrupada por família de produto ──────────────────────────────
        if ir.intent == "producao_por_familia":
            top_n = ir.top_n or 10
            rows = self.kardex.get_producao_por_familia(
                ini, fim, limite=top_n, origem=ir.origem,
            )
            if not rows:
                return f"🔍 Nenhum dado de produção por família encontrado{periodo}."
            header = f"🏷️ **Produção por família de produto**{periodo}\n\n"
            header += "| # | Família | Total KG | Registros |\n|---|---------|----------|----------|\n"
            linhas = "\n".join(
                f"| {_posicao_label(r['posicao'])} | {r['familia']} "
                f"| **{_fmt_kg(r['total_kg'])}** | {r['registros']} |"
                for r in rows
            )
            return header + linhas

        return "Solicitação recebida, mas ainda não há tratativa para este tipo de consulta."

    # ── Comparação entre dois períodos ───────────────────────────────────────

    def _handle_comparacao_periodos(self, ir: InterpretationResult) -> str:
        """
        Executa a mesma consulta em dois períodos distintos e exibe a variação.

        Suporta métricas: producao_total, geracao_ld, revisao_kg.
        Se entity_value estiver definido, filtra pelo operador.
        """
        ini1, fim1, lbl1 = ir.data_inicio, ir.data_fim, ir.period_text or ir.data_inicio
        ini2, fim2, lbl2 = ir.data_inicio2, ir.data_fim2, ir.period_text2 or ir.data_inicio2

        if not (ini1 and fim1 and ini2 and fim2):
            return (
                "Não consegui identificar os dois períodos para comparação.\n\n"
                "Tente: _\"compare a produção de janeiro com fevereiro\"_ "
                "ou _\"diferença de LD desta semana com a semana passada\"_."
            )

        rec_lbl = self._recurso_label(ir.recursos)

        if ir.metric == "geracao_ld":
            if ir.entity_value:
                d1 = self.kardex.get_ld_por_operador(ir.entity_value, ini1, fim1, origem=ir.origem)
                d2 = self.kardex.get_ld_por_operador(ir.entity_value, ini2, fim2, origem=ir.origem)
                titulo = f"⚠️ **LD — {ir.entity_value}**: {lbl1} vs {lbl2}"
            else:
                d1 = self.kardex.get_ld_total(ini1, fim1, origem=ir.origem)
                d2 = self.kardex.get_ld_total(ini2, fim2, origem=ir.origem)
                titulo = f"⚠️ **Comparativo de LD**: {lbl1} vs {lbl2}"
            v1 = float(d1.get("KG", 0))
            v2 = float(d2.get("KG", 0))
            fmt = _fmt_kg

        elif ir.metric == "revisao_kg":
            rows1 = self.apont_rev.get_ranking_revisao(ini1, fim1, top_n=200, operadores=OPERADORES_REVISAO)
            rows2 = self.apont_rev.get_ranking_revisao(ini2, fim2, top_n=200, operadores=OPERADORES_REVISAO)
            v1 = sum(r["total_metros"] for r in rows1)
            v2 = sum(r["total_metros"] for r in rows2)
            titulo = f"📋 **Comparativo de Revisão**: {lbl1} vs {lbl2}"
            fmt = _fmt_metros

        else:  # producao_total
            v1 = float(self.sql.get_producao_total(ini1, fim1, recursos=ir.recursos))
            v2 = float(self.sql.get_producao_total(ini2, fim2, recursos=ir.recursos))
            titulo = f"⚙️ **Comparativo de Produção**: {lbl1} vs {lbl2}"
            fmt = _fmt_kg

        # Calcula variação
        if v1 > 0:
            variacao = ((v2 - v1) / v1) * 100
            diff = abs(v2 - v1)
            sinal = "+" if variacao >= 0 else ""
            if v2 > v1:
                tendencia = f"↗️ Aumento de **{fmt(diff)}** ({sinal}{variacao:.1f}%)"
            elif v2 < v1:
                tendencia = f"↘️ Queda de **{fmt(diff)}** ({variacao:.1f}%)"
            else:
                tendencia = "→ Sem variação entre os períodos"
        elif v2 > 0:
            tendencia = f"↗️ {lbl2} saiu do zero — sem dados comparáveis em {lbl1}"
        else:
            tendencia = "→ Sem dados em ambos os períodos"

        return (
            f"{titulo}{rec_lbl}\n\n"
            f"| Período | Total |\n|---------|-------|\n"
            f"| {lbl1} | **{fmt(v1)}** |\n"
            f"| {lbl2} | **{fmt(v2)}** |\n\n"
            f"{tendencia}"
        )

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
