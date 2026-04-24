"""
config.py — Configurações de negócio do ViniAI. FONTE DA VERDADE.

Contém toda a definição de setores, operadores e tipos de movimentação.
Qualquer alteração de operadores ou setores deve ser feita APENAS aqui.

Conceitos de negócio
────────────────────
  extrusora  → operadores que PRODUZEM material nas máquinas MAC1/MAC2.
               Dados consultados via dbo.STG_PROD_SH6_VPLONAS (sql_service_sh6.py).

  revisao    → operadores que REVISAM o material produzido.
               Identificam LD (defeito=Y) ou Inteiro (sem defeito=I).
               Dados consultados via dbo.V_KARDEX (sql_service_kardex.py).

Regra de roteamento por setor
──────────────────────────────
  Operador em extrusora → query vai para SH6 (produção)
  Operador em revisao   → query vai para KARDEX (qualidade)
  Operador desconhecido → ignorar por enquanto

Estrutura do código de produto
──────────────────────────────
  Exemplo: TD2AYBR1BOBR100
    TD2 → tipo de material (posições 1–3)
    A   → variante (posição 4)
    Y   → indicador: Y=LD (defeito), I=Inteiro (posição 5)
    BR1 → código de cor
    BO  → tipo de tecido/acabamento
    BR100 → dimensão/tamanho
"""
from __future__ import annotations

# ── Setores e operadores ──────────────────────────────────────────────────────

SETORES: dict[str, dict] = {
    "extrusora": {
        "label": "Extrusora",
        "descricao": "Operadores da extrusora — produzem material (MAC1/MAC2). Consultados via SH6.",
        "operadores": [
            "celio.divino",
            "aramis.leal",
            "valdenrique.silva",
            "andreson.reis",
            "ednilson.soares",
            "nobrega.valter",
            "gilmar.santos",
        ],
    },
    "revisao": {
        "label": "Revisão",
        "descricao": "Revisores — inspecionam o material e identificam LD (Y) ou Inteiro (I). Consultados via KARDEX.",
        "operadores": [
            "raul.ribeiro",
            "kaua.chagas",
            "ezequiel.nunes",
            "igor.chiva",
        ],
    },
}

# ── Listas por setor (atalhos para uso no orchestrator) ───────────────────────
OPERADORES_EXTRUSORA: list[str] = SETORES["extrusora"]["operadores"]
OPERADORES_REVISAO:   list[str] = SETORES["revisao"]["operadores"]

# Todos os operadores ativos — used para filtros gerais e auto-inject
OPERADORES_ATIVOS: list[str] = OPERADORES_EXTRUSORA + OPERADORES_REVISAO

# ── Tipos de movimentação (coluna `origem` na view) ───────────────────────────
ORIGENS: dict[str, str] = {
    "SD1": "Entrada",
    "SD2": "Saída",
    "SD3": "Movimentação Interna",
}


# ── Funções auxiliares ────────────────────────────────────────────────────────

def get_label_setor(setor: str) -> str:
    """Retorna o nome legível do setor (ex: 'revisao' → 'Revisão')."""
    return SETORES.get(setor, {}).get("label", setor.capitalize())


def get_setor_de(operador: str) -> str | None:
    """Retorna o setor de um operador ('extrusora' | 'revisao' | None)."""
    for setor, dados in SETORES.items():
        if operador.lower() in dados["operadores"]:
            return setor
    return None


def get_operadores_setor(setor: str) -> list[str]:
    """Retorna a lista de operadores de um setor (aceita variações de nome)."""
    chave = _normalizar_setor(setor)
    return list(SETORES.get(chave, {}).get("operadores", []))


def todos_operadores() -> list[str]:
    """Retorna todos os operadores cadastrados em qualquer setor."""
    return [op for dados in SETORES.values() for op in dados["operadores"]]


def _normalizar_setor(setor: str) -> str:
    """Normaliza variações de nome de setor para a chave interna."""
    aliases = {
        "extrusora":  "extrusora",
        "producao":   "extrusora",  # alias histórico
        "produção":   "extrusora",  # alias histórico
        "revisao":    "revisao",
        "revisão":    "revisao",
        # expedição mantida para compatibilidade com código legado (sem operadores)
        "expedicao":  "expedicao",
        "expedição":  "expedicao",
        "expedicão":  "expedicao",
    }
    return aliases.get(setor.lower().strip(), setor.lower().strip())
