"""
permissions.py — Controle de acesso e conformidade LGPD.

Define quais agentes/domínios cada perfil de usuário pode acessar.

Lógica de restrição
────────────────────
  A restrição NÃO é dentro do mesmo agente (ex: revisão vs. expedição são
  ambos parte da Produção e um usuário de produção vê tudo da Ayla).

  A restrição é ENTRE departamentos: um usuário de RH não deve acessar
  dados de Produção (Ayla), e um usuário de Produção não deve acessar
  dados financeiros (Maya), por exemplo.

Perfis disponíveis
──────────────────
  admin / gerencia / ti  → acesso irrestrito a todos os agentes
  producao               → acesso total ao agente Ayla (Produção)
  rh                     → acesso ao agente Nina (RH) — futuro
  vendas                 → acesso ao agente Eva (Vendas) — futuro
  controladoria          → acesso ao agente Maya — futuro
  (vazio / None)         → sem restrição (compatibilidade retroativa)

Como funciona
─────────────
  1. O frontend envia `user_setor` no payload (ex: "producao", "rh").
  2. O orchestrator chama `verificar_permissao(user_setor, agent_id, intent)`.
  3. Se negado, retorna `MENSAGEM_LGPD` ao usuário sem executar a query.

Intents livres
──────────────
  smalltalk, clarify e tipos_informacao são sempre liberados para qualquer
  perfil — conversa natural e apresentação do agente não são dados sensíveis.
"""
from __future__ import annotations

# ── Intents sempre liberados (conversa, ajuda, saudações) ─────────────────────
_INTENTS_LIVRES = {
    "smalltalk",
    "clarify",
    "tipos_informacao",
}

# ── Agentes acessíveis por perfil ─────────────────────────────────────────────
# None = sem restrição (acesso a todos os agentes).
# set  = conjunto de agent_ids permitidos.
_AGENTES_POR_PERFIL: dict[str, set[str] | None] = {
    # Gestão e TI — acesso total
    "admin":          None,
    "gerencia":       None,
    "ti":             None,

    # Produção (inclui revisão, expedição, extrusora) → Ayla
    "producao":       {"producao"},

    # Futuros departamentos — liberar conforme os agentes forem implementados
    "rh":             {"rh"},
    "vendas":         {"vendas"},
    "controladoria":  {"controladoria"},
    "pcp":            {"pcp"},
    "pesagem":        {"pesagem"},
    "qualidade":      {"qualidade"},
    "logistica":      {"logistica"},
}

# ── Mensagem formal de LGPD ───────────────────────────────────────────────────
MENSAGEM_LGPD = """\
## Acesso Negado — Proteção de Dados Pessoais (LGPD)

Esta solicitação envolve informações que **não estão dentro do escopo de acesso \
autorizado** para o seu perfil de usuário.

De acordo com a **Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018 — LGPD)** \
e com as políticas internas de segurança da informação da **Viniplast**, o acesso a dados \
de outros departamentos ou além do nível hierárquico do colaborador requer autorização \
expressa do responsável pelo tratamento de dados (DPO) ou da gestão competente.

Os dados tratados por este sistema são classificados e protegidos com base nos seguintes \
princípios definidos pela LGPD:

- **Finalidade** — os dados são coletados e utilizados para fins específicos, explícitos e legítimos;
- **Necessidade** — apenas os dados estritamente indispensáveis ao exercício da função são acessados;
- **Acesso mínimo** — cada colaborador acessa somente as informações inerentes ao seu cargo e departamento;
- **Segurança** — medidas técnicas e administrativas são adotadas para proteger os dados de acessos não autorizados.

---

Caso você entenda que este acesso seja necessário para o exercício de suas atividades \
profissionais, solicite a liberação formal junto ao seu **gestor imediato** ou ao **setor de TI**.

> *Referência legal: Art. 6º, incisos I, III, V e VII, da Lei nº 13.709/2018 (LGPD).*\
"""


# ── Função de verificação ─────────────────────────────────────────────────────

def verificar_permissao(
    user_setor: str | None,
    agent_id: str,
    intent: str,
) -> bool:
    """
    Retorna True se o perfil do usuário tem permissão para acessar o agente/intent.

    Regras:
      - Intents livres (smalltalk, clarify, tipos_informacao) → sempre permitido.
      - user_setor None ou vazio → sem restrição (retrocompatibilidade).
      - Perfil não mapeado → sem restrição (evita bloquear perfis futuros).
      - Perfil mapeado com None → acesso total (admin/gerencia/ti).
      - Perfil mapeado com set → verifica se agent_id está no conjunto.
    """
    # Intents de conversa e ajuda são sempre liberados
    if intent in _INTENTS_LIVRES:
        return True

    # Sem setor informado = sem restrição (retrocompatibilidade)
    if not user_setor:
        return True

    setor = user_setor.strip().lower()
    regra = _AGENTES_POR_PERFIL.get(setor)

    # Perfil não mapeado ou regra None = acesso total
    if regra is None:
        return True

    return agent_id in regra
