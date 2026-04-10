"""
permissions.py — Controle de acesso e conformidade LGPD.

Define quais intents (consultas) cada setor/perfil de usuário pode executar.
Quando uma solicitação ultrapassa o escopo autorizado, retorna mensagem formal
baseada na Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018).

Perfis disponíveis
──────────────────
  admin / gerencia  → acesso irrestrito
  producao          → dados de produção e totais gerais
  revisao           → dados de LD, revisão e rankings de qualidade
  expedicao         → movimentações do próprio setor
  (vazio / None)    → sem restrição (compatibilidade retroativa)

Como funciona
─────────────
  1. O frontend envia `user_setor` no payload (ex: "revisao").
  2. O orchestrator chama `verificar_permissao(user_setor, intent)`.
  3. Se negado, retorna `MENSAGEM_LGPD` ao usuário sem executar a query.
"""
from __future__ import annotations

# ── Intents permitidos por setor ──────────────────────────────────────────────
# None significa sem restrição (acesso total).
# Intents "smalltalk", "clarify" e "tipos_informacao" são sempre liberados.

_LIVRES = {
    "smalltalk",
    "clarify",
    "tipos_informacao",
    "periodos_disponiveis",
    "list_operadores_revisao",
}

_PERMISSOES: dict[str, set[str] | None] = {
    # Gestão e TI — sem restrição
    "admin":    None,
    "gerencia": None,
    "ti":       None,

    # Produção — consultas de volume e ranking de produção
    "producao": _LIVRES | {
        "ranking_producao_geral",
        "producao_por_operador",
        "producao_por_turno",
        "producao_por_produto",
        "total_fabrica",
    },

    # Revisão — dados de LD e qualidade
    "revisao": _LIVRES | {
        "ranking_usuarios_ld",
        "ranking_produtos_ld",
        "geracao_ld_por_operador",
        "total_fabrica",
    },

    # Expedição — movimentações do próprio setor
    "expedicao": _LIVRES | {
        "producao_por_operador",
        "total_fabrica",
    },
}

# ── Mensagem formal de LGPD ───────────────────────────────────────────────────
MENSAGEM_LGPD = """\
## Acesso Negado — Proteção de Dados (LGPD)

Esta solicitação envolve informações que **não estão dentro do escopo de acesso \
autorizado** para o seu perfil de usuário.

De acordo com a **Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018 — LGPD)** \
e com as políticas internas de segurança da informação da **Viniplast**, o acesso a dados \
de outros setores ou além do nível hierárquico do colaborador requer autorização expressa \
do responsável pelo tratamento de dados (DPO) ou da gestão competente.

Os dados tratados por este sistema são classificados e protegidos com base nos seguintes \
princípios definidos pela LGPD:

- **Finalidade** — os dados são coletados e utilizados para fins específicos, explícitos e legítimos;
- **Necessidade** — apenas os dados estritamente indispensáveis ao exercício da função são acessados;
- **Acesso mínimo** — cada colaborador acessa somente as informações inerentes ao seu cargo e setor;
- **Segurança** — medidas técnicas e administrativas são adotadas para proteger os dados de acessos não autorizados.

---

Caso você entenda que este acesso seja necessário para o exercício de suas atividades \
profissionais, solicite a liberação formal junto ao seu **gestor imediato** ou ao **setor de TI**.

> *Referência legal: Art. 6º, incisos I, III, V e VII, da Lei nº 13.709/2018 (LGPD).*\
"""


# ── Função de verificação ─────────────────────────────────────────────────────

def verificar_permissao(user_setor: str | None, intent: str) -> bool:
    """
    Retorna True se o setor do usuário tem permissão para executar o intent.

    Regras:
      - user_setor None ou vazio → sem restrição (retrocompatibilidade).
      - Setor não mapeado → sem restrição (evita bloquear perfis futuros).
      - Setor mapeado com None → acesso total (admin/gerencia).
      - Setor mapeado com set → verifica se o intent está no conjunto.
    """
    if not user_setor:
        return True

    setor = user_setor.strip().lower()
    regra = _PERMISSOES.get(setor)

    # Setor não mapeado ou regra None = acesso total
    if regra is None:
        return True

    return intent in regra
