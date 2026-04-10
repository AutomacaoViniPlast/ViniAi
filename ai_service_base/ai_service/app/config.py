"""
config.py — Configurações de negócio do ViniAI. FONTE DA VERDADE.

Contém toda a definição de setores, operadores e tipos de movimentação.
Qualquer alteração de operadores ou setores deve ser feita APENAS aqui.

Conceitos de negócio
────────────────────
  producao  → material que saiu da extrusora. Ranking padrão de "produção".
  revisao   → inspeção de qualidade do material. Identifica LD (defeito) ou I (inteiro).
              Os números da revisão representam o que foi inspecionado, NÃO produzido.
  expedicao → liberação de bobinas para clientes. Não produzem — apenas movimentam.
              NUNCA entram em rankings de produção.

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
    "producao": {
        "label": "Produção",
        "descricao": "Operadores da extrusora — geram o material bruto.",
        # Preenchido conforme operadores forem cadastrados.
        "operadores": [],
    },
    "revisao": {
        "label": "Revisão",
        "descricao": "Inspecionam o material e identificam defeitos (LD) ou material inteiro.",
        "operadores": [
            "raul.araujo",
            "igor.chiva",
            "ezequiel.nunes",
        ],
    },
    "expedicao": {
        "label": "Expedição",
        "descricao": "Liberam bobinas para clientes. Não participam de rankings de produção.",
        "operadores": [
            "john.moraes",
            "rafael.paiva",
            "andre.prado",
            "richard.santos",
            "arilson.aguiar",
        ],
    },
    # Futuros setores: adicionar aqui conforme necessário.
    # "corte":   {"label": "Corte",   "descricao": "...", "operadores": []},
    # "costura": {"label": "Costura", "descricao": "...", "operadores": []},
}

# ── Escopo padrão de operadores ativos ───────────────────────────────────────
# Consultas sem setor explícito se restringem a esta lista.
# Para ampliar o escopo, basta adicionar operadores aqui.
OPERADORES_ATIVOS: list[str] = [
    "ezequiel.nunes",
    "raul.araujo",
    "kaua.chagas",
    "igor.chiva",
]

# ── Tipos de movimentação (coluna `origem` na view) ───────────────────────────
ORIGENS: dict[str, str] = {
    "SD1": "Entrada",
    "SD2": "Saída",
    "SD3": "Movimentação Interna",
}

# ── Setores excluídos de rankings de produção ─────────────────────────────────
_EXCLUIDOS_DA_PRODUCAO = {"expedicao"}


# ── Funções auxiliares ────────────────────────────────────────────────────────

def get_label_setor(setor: str) -> str:
    """Retorna o nome legível do setor (ex: 'revisao' → 'Revisão')."""
    return SETORES.get(setor, {}).get("label", setor.capitalize())


def get_setor_de(operador: str) -> str | None:
    """Retorna o setor de um operador, ou None se não cadastrado."""
    for setor, dados in SETORES.items():
        if operador.lower() in dados["operadores"]:
            return setor
    return None


def get_operadores_setor(setor: str) -> list[str]:
    """Retorna a lista de operadores de um setor (aceita variações de nome)."""
    chave = _normalizar_setor(setor)
    return list(SETORES.get(chave, {}).get("operadores", []))


def get_excluidos_producao() -> list[str]:
    """Retorna todos os operadores que não devem entrar em rankings de produção."""
    excluidos = []
    for setor in _EXCLUIDOS_DA_PRODUCAO:
        excluidos.extend(SETORES.get(setor, {}).get("operadores", []))
    return excluidos


def todos_operadores() -> list[str]:
    """Retorna todos os operadores cadastrados em qualquer setor."""
    return [op for dados in SETORES.values() for op in dados["operadores"]]


def _normalizar_setor(setor: str) -> str:
    """Normaliza variações de nome de setor para a chave interna."""
    aliases = {
        "producao":  "producao",
        "produção":  "producao",
        "expedicao": "expedicao",
        "expedição": "expedicao",
        "expedicão": "expedicao",
        "revisao":   "revisao",
        "revisão":   "revisao",
    }
    return aliases.get(setor.lower().strip(), setor.lower().strip())
