from __future__ import annotations

from app.config import OPERADORES_ATIVOS, ORIGENS, SETORES, get_excluidos_producao, get_label_setor, get_operadores_setor, get_setor_de
from app.context_manager import PostgresContextManager
from app.interpreter import InterpretationResult, RuleBasedInterpreter
from app.schemas import ChatProcessRequest, ChatProcessResponse
from app.sql_service import SQLService

# Expedição não entra em rankings de produção (só libera bobinas para clientes)
_EXCLUIDOS_PRODUCAO = get_excluidos_producao()


def _fmt_kg(valor: float) -> str:
    return f"{valor:,.2f} KG".replace(",", "X").replace(".", ",").replace("X", ".")


def _periodo_label(ir: InterpretationResult) -> str:
    if ir.period_text:
        return f" em {ir.period_text}"
    if ir.data_inicio and ir.data_fim:
        return f" de {ir.data_inicio} a {ir.data_fim}"
    return ""


def _origem_label(origem: str | None) -> str:
    if not origem:
        return ""
    nome = ORIGENS.get(origem, origem)
    return f" [{nome}]"


class ChatOrchestrator:
    def __init__(self) -> None:
        self.context     = PostgresContextManager()
        self.interpreter = RuleBasedInterpreter()
        self.sql         = SQLService()

    def process(self, payload: ChatProcessRequest) -> ChatProcessResponse:
        self.context.append_user_message(payload.session_id, payload.message)
        recent = self.context.get_recent(payload.session_id, limit=6)
        ir     = self.interpreter.interpret(payload.message)

        # ── Capacidades ───────────────────────────────────────────────────────
        if ir.intent == "tipos_informacao":
            answer = (
                "### O que consigo responder\n\n"
                "**LD (Material com defeito — revisão)**\n"
                "- \"Quem gerou mais LD em janeiro de 2026?\"\n"
                "- \"Top 5 com mais LD em 2025\"\n"
                "- \"Quanto o ezequiel.nunes identificou de LD em março?\"\n"
                "- \"Qual produto gerou mais LD no mês passado?\"\n\n"
                "**Produção geral**\n"
                "- \"Ranking de produção em 2025\"\n"
                "- \"Quanto o kaua.chagas produziu em fevereiro de 2026?\"\n"
                "- \"Produção por turno em março de 2026\"\n"
                "- \"Total geral em 2025\"\n\n"
                "**Setores**\n"
                "- \"Operadores da revisão\"\n"
                "- \"Operadores da expedição\"\n"
                "- \"Top 3 da revisão com mais LD em 2026\"\n\n"
                "**Períodos**\n"
                "- Qualquer mês/ano: \"em jan de 2026\", \"em março\", \"em 2025\"\n"
                "- Atalhos: \"este mês\", \"mês passado\", \"este ano\", \"ano passado\"\n\n"
                "**Tipos de movimentação**\n"
                "- \"Top 5 LD em SD3\" (Movimentação Interna)\n"
                "- `SD1` = Entrada · `SD2` = Saída · `SD3` = Movimentação Interna\n\n"
                "---\n"
                "Cobertura de dados: **Jul/2019** até o mês atual.\n"
                "Digite \"quais meses você tem dados?\" para ver os períodos disponíveis."
            )
            self.context.append_assistant_message(payload.session_id, answer)
            return self._ok(answer, ir)

        # ── Smalltalk ─────────────────────────────────────────────────────────
        if ir.route == "smalltalk":
            answer = (
                "Olá! Sou o **ViniAI**, assistente de produção da fábrica.\n\n"
                "Posso te ajudar com **LD**, **produção**, **rankings**, **turnos** e muito mais.\n"
                "Digite \"o que você sabe fazer?\" para ver todas as possibilidades.\n\n"
                "Como posso ajudar?"
            )
            self.context.append_assistant_message(payload.session_id, answer)
            return self._ok(answer, ir)

        # ── Clarificação ──────────────────────────────────────────────────────
        if ir.route == "clarify":
            answer = (
                "Não entendi sua solicitação. Tente reformular com algo como:\n\n"
                "- \"Quem mais produziu LD em janeiro de 2026?\"\n"
                "- \"Top 5 da expedição com mais LD em 2025\"\n"
                "- \"Qual produto gerou mais LD no mês passado?\"\n"
                "- \"Produção da revisão em março de 2026\"\n"
                "- \"Quanto o ezequiel.nunes produziu?\"\n"
                "- \"Produção por turno em 2025\"\n"
                "- \"Total da fábrica em SD3\""
            )
            self.context.append_assistant_message(payload.session_id, answer)
            return self._ok(answer, ir, requires_clarification=True)

        # ── SQL ───────────────────────────────────────────────────────────────
        answer = self._handle_sql(ir)
        self.context.append_assistant_message(payload.session_id, answer)
        return ChatProcessResponse(
            status="ok",
            answer=answer,
            route=ir.route,
            confidence=ir.confidence,
            used_sql=True,
            debug={
                "intent": ir.intent,
                "metric": ir.metric,
                "entity_type": ir.entity_type,
                "entity_value": ir.entity_value,
                "period_text": ir.period_text,
                "data_inicio": ir.data_inicio,
                "data_fim": ir.data_fim,
                "top_n": ir.top_n,
                "setor": ir.setor,
                "origem": ir.origem,
                "history_size": len(recent),
                "reasoning": ir.reasoning,
            },
        )

    # ── Handler SQL ───────────────────────────────────────────────────────────

    def _handle_sql(self, ir: InterpretationResult) -> str:
        try:
            return self._dispatch(ir)
        except Exception as exc:
            return f"Ocorreu um erro ao consultar o banco de dados: {exc}"

    def _dispatch(self, ir: InterpretationResult) -> str:
        periodo  = _periodo_label(ir)
        orig_lbl = _origem_label(ir.origem)
        ini      = ir.data_inicio or "01/01/2025"
        fim      = ir.data_fim    or "31/12/2026"
        top_n    = ir.top_n       or 5
        origem   = ir.origem      # pode ser None
        setor    = ir.setor       # pode ser None

        # Setor explicitamente solicitado → filtra só aquele setor
        # Sem setor → usa OPERADORES_ATIVOS como escopo padrão
        if setor:
            filtro_usuarios = get_operadores_setor(setor)
            setor_label     = get_label_setor(setor)
        else:
            filtro_usuarios = list(OPERADORES_ATIVOS)
            setor_label     = None

        excluir_lista: list[str] | None = None  # não precisa mais excluir, já filtramos

        # ── Períodos disponíveis ──────────────────────────────────────────────
        if ir.intent == "periodos_disponiveis":
            _MESES_NOME = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
            periodos = self.sql.get_periodos_disponiveis(filtro_usuarios)
            if not periodos:
                return "Não encontrei dados no banco para os operadores ativos."

            linhas = []
            avisos = []
            for p in periodos:
                ano   = p["ano"]
                meses = p["meses"]
                todos = list(range(1, 13))
                if meses == todos:
                    linhas.append(f"- **{ano}**: ano completo (Jan–Dez)")
                else:
                    nomes = ", ".join(_MESES_NOME[m - 1] for m in meses)
                    linhas.append(f"- **{ano}**: {nomes}")
                    if len(meses) < 6:
                        avisos.append(f"{ano} (dados esparsos — {len(meses)} meses)")

            corpo = "\n".join(linhas)
            nota  = ""
            if avisos:
                nota = "\n\n> ⚠️ Dados incompletos em: " + ", ".join(avisos)
            nota += "\n\n> Para consultas confiáveis, recomendo usar **2022 em diante**."

            return f"### Períodos com dados disponíveis\n\n{corpo}{nota}"

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
        # "quem gerou mais LD" é uma pergunta de revisão, não de produção
        if ir.intent == "ranking_usuarios_ld":
            rows = self.sql.get_ranking_usuarios_ld(
                ini, fim, top_n, origem,
                filtro_usuarios=filtro_usuarios,
                excluir_usuarios=excluir_lista if not setor else None,
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

        # ── Ranking produtos por LD ───────────────────────────────────────────
        if ir.intent == "ranking_produtos_ld":
            rows = self.sql.get_ranking_produtos_ld(
                ini, fim, top_n, origem,
                filtro_usuarios=filtro_usuarios,
                excluir_usuarios=excluir_lista if not setor else None,
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
                    "Não identifiquei o operador. "
                    "Informe o nome (ex: ezequiel.nunes ou só 'Ezequiel')."
                )
            setor_op   = get_setor_de(ir.entity_value)
            setor_info = f" ({get_label_setor(setor_op)})" if setor_op else ""
            total = self.sql.get_ld_por_operador(ir.entity_value, ini, fim, origem)
            if float(total) == 0:
                return (
                    f"Nenhum LD identificado por {ir.entity_value}{setor_info}{periodo}{orig_lbl}.\n"
                    "Verifique o nome ou o período informado."
                )
            return (
                f"### LD identificado em revisão\n\n"
                f"**Operador:** {ir.entity_value}{setor_info}  \n"
                f"**Período:** {periodo.strip() or 'geral'}  \n"
                f"**Total:** {_fmt_kg(float(total))}"
            )

        # ── Movimentação da expedição por operador ────────────────────────────
        if ir.intent == "producao_por_operador":
            if not ir.entity_value:
                return (
                    "Não identifiquei o operador. "
                    "Informe o nome (ex: john.moraes ou só 'John')."
                )
            setor_op   = get_setor_de(ir.entity_value)
            setor_info = f" ({get_label_setor(setor_op)})" if setor_op else ""

            # Se for expedição, nomear corretamente
            if setor_op == "expedicao":
                total = self.sql.get_producao_por_operador(ir.entity_value, ini, fim, origem)
                if float(total) == 0:
                    return (
                        f"Nenhuma movimentação encontrada para {ir.entity_value}{setor_info}{periodo}{orig_lbl}.\n"
                        "Verifique o nome ou o período informado."
                    )
                return (
                    f"### Bobinas liberadas — Expedição\n\n"
                    f"**Operador:** {ir.entity_value}  \n"
                    f"**Período:** {periodo.strip() or 'geral'}  \n"
                    f"**Total movimentado:** {_fmt_kg(float(total))}"
                )

            total = self.sql.get_producao_por_operador(ir.entity_value, ini, fim, origem)
            if float(total) == 0:
                return (
                    f"Nenhum registro encontrado para **{ir.entity_value}**{setor_info}{periodo}{orig_lbl}.\n"
                    "Verifique o nome ou o período informado."
                )
            return (
                f"### Produção\n\n"
                f"**Operador:** {ir.entity_value}{setor_info}  \n"
                f"**Período:** {periodo.strip() or 'geral'}  \n"
                f"**Total:** {_fmt_kg(float(total))}"
            )

        # ── Produção por produto específico ───────────────────────────────────
        if ir.intent == "producao_por_produto":
            if not ir.entity_value:
                return "Não identifiquei o código do produto. Informe o código (ex: TD2AYBR1BOBR100)."
            total = self.sql.get_producao_por_produto(ir.entity_value, ini, fim, origem)
            if float(total) == 0:
                return f"Nenhuma produção encontrada para {ir.entity_value}{periodo}{orig_lbl}."
            return (
                f"### Produção por produto\n\n"
                f"**Produto:** `{ir.entity_value}`  \n"
                f"**Período:** {periodo.strip() or 'geral'}  \n"
                f"**Total:** {_fmt_kg(float(total))}"
            )

        # ── Ranking geral de produção (exclui expedição por padrão) ──────────
        if ir.intent == "ranking_producao_geral":
            rows = self.sql.get_ranking_producao_geral(
                ini, fim, top_n, origem,
                filtro_usuarios=filtro_usuarios,
                excluir_usuarios=excluir_lista if not setor else None,
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

        # ── Produção por turno (exclui expedição por padrão) ─────────────────
        if ir.intent == "producao_por_turno":
            rows = self.sql.get_producao_por_turno(
                ini, fim, origem,
                filtro_usuarios=filtro_usuarios,
                excluir_usuarios=excluir_lista if not setor else None,
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

        # ── Total da fábrica ──────────────────────────────────────────────────
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

    # ── Helper ────────────────────────────────────────────────────────────────

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
            debug={"intent": ir.intent, "reasoning": ir.reasoning},
        )
