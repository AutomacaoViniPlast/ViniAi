"""
permissions.py — Controle de acesso e conformidade LGPD.

Estrutura organizacional da Viniplast
──────────────────────────────────────
  A empresa é dividida em DEPARTAMENTOS. Cada departamento tem acesso
  apenas aos agentes de IA do seu próprio domínio.

  Departamento PRODUÇÃO
  ├── Extrusora  → Ayla        (agent_id: "producao")
  ├── Pesagem    → Lara        (agent_id: "pesagem")
  ├── Qualidade  → Luna        (agent_id: "qualidade")
  └── Expedição  → Vera        (agent_id: "logistica")

  Departamento PCP (Planejamento e Controle de Produção)
  └── PCP        → Iris        (agent_id: "pcp")

  Departamento RH
  └── RH         → Nina        (agent_id: "rh")

  Departamento CONTROLADORIA
  └── Financeiro → Maya        (agent_id: "controladoria")

  Departamento VENDAS
  └── Vendas     → Eva         (agent_id: "vendas")

  Gestão / TI → acesso irrestrito a todos os agentes

Regra geral
───────────
  Um usuário do departamento X acessa APENAS os agentes do departamento X.
  Nenhum departamento acessa dados de outro — exceto Admin, Gerência e TI.

Intents sempre liberados
─────────────────────────
  smalltalk, clarify e tipos_informacao não são dados sensíveis.
  São liberados para qualquer perfil — saudações e apresentação do agente
  não precisam de controle de acesso.

Como funciona
─────────────
  1. Frontend envia `user_setor` no payload (ex: "producao", "rh").
  2. Orchestrator chama `verificar_permissao(user_setor, agent_id, intent)`.
  3. Se negado: retorna MENSAGEM_LGPD. Query SQL não é executada.
"""
from __future__ import annotations

# ── Intents sempre liberados para qualquer perfil ─────────────────────────────
_INTENTS_LIVRES = {
    "smalltalk",
    "clarify",
    "tipos_informacao",
}

# ── Agentes de cada departamento (sub-áreas inclusas) ────────────────────────
# None = sem restrição (acesso a todos os agentes).
# set  = agent_ids que esse departamento pode acessar.

_AGENTES_POR_DEPARTAMENTO: dict[str, set[str] | None] = {

    # ── Gestão e TI — acesso total ────────────────────────────────────────────
    "admin":    None,
    "gerencia": None,
    "ti":       None,

    # ── Produção — acessa todos os agentes das sub-áreas de produção ──────────
    # Sub-áreas: Extrusora (Ayla), Pesagem (Lara), Qualidade (Luna), Expedição (Vera)
    "producao": {
        "producao",   # Ayla   — Extrusora / dados gerais de produção
        "pesagem",    # Lara   — Pesagem de bobinas
        "qualidade",  # Luna   — Controle de qualidade
        "logistica",  # Vera   — Expedição / logística
    },

    # ── PCP — Planejamento e Controle de Produção ─────────────────────────────
    # Acessa o agente de PCP e também dados de produção (necessário para planejamento)
    "pcp": {
        "pcp",        # Iris   — PCP
        "producao",   # Ayla   — consulta de dados de produção para planejar
    },

    # ── RH — Recursos Humanos ─────────────────────────────────────────────────
    "rh": {
        "rh",         # Nina   — RH
    },

    # ── Controladoria — Financeiro e Custos ───────────────────────────────────
    "controladoria": {
        "controladoria",  # Maya — Controladoria
    },

    # ── Vendas ────────────────────────────────────────────────────────────────
    "vendas": {
        "vendas",     # Eva    — Vendas
    },
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
    Retorna True se o departamento do usuário tem permissão para acessar o agente.

    Parâmetros:
      user_setor : departamento do usuário autenticado (ex: "producao", "rh")
      agent_id   : ID do agente sendo acessado (ex: "producao", "pesagem")
      intent     : intenção detectada pelo interpretador

    Regras:
      - Intents livres (smalltalk, clarify, tipos_informacao) → sempre permitido.
      - user_setor None/vazio → sem restrição (retrocompatibilidade).
      - Departamento não mapeado → sem restrição (evita bloquear perfis futuros).
      - Departamento com None → acesso total (admin/gerencia/ti).
      - Departamento com set → verifica se agent_id está no conjunto.
    """
    if intent in _INTENTS_LIVRES:
        return True

    if not user_setor:
        return True

    depto = user_setor.strip().lower()
    regra = _AGENTES_POR_DEPARTAMENTO.get(depto)

    # Não mapeado ou None = acesso total
    if regra is None:
        return True

    return agent_id in regra
