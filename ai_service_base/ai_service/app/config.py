"""
Configurações de negócio do ViniAI.

Conceitos:
  - producao  → material que saiu da extrusora. Ranking padrão de "produção".
  - revisao   → processo de revisão de qualidade. Identifica LD (defeito) ou I (inteiro).
                Não é produção — é inspeção do material produzido.
  - expedicao → liberação de bobinas para clientes. Não produzem, apenas movimentam.

Para adicionar operadores ou setores: edite apenas este arquivo.
"""
from __future__ import annotations

# ── Setores, tipo e operadores ────────────────────────────────────────────────
SETORES: dict[str, dict] = {
    "producao": {
        "label": "Produção",
        "descricao": "Operadores da extrusora — geram o material.",
        # Preenchido conforme operadores forem cadastrados.
        # Consultas de "produção" excluem expedição e revisão por padrão.
        "operadores": [],
    },
    "revisao": {
        "label": "Revisão",
        "descricao": "Operadores que inspecionam o material e identificam defeitos (LD).",
        "operadores": [
            "raul.araujo",
            "igor.chiva",
            "ezequiel.nunes",
        ],
    },
    "expedicao": {
        "label": "Expedição",
        "descricao": "Operadores que liberam bobinas para clientes. Não participam de rankings de produção.",
        "operadores": [
            "john.moraes",
            "rafael.paiva",
            "andre.prado",
            "richard.santos",
            "arilson.aguiar",
        ],
    },
    # Futuros setores: adicionar aqui
    # "corte":    {"label": "Corte",    "descricao": "...", "operadores": [...]},
    # "costura":  {"label": "Costura",  "descricao": "...", "operadores": [...]},
}

# ── Operadores ativos no escopo atual ────────────────────────────────────────
# Todas as consultas sem setor explícito se restringem a esta lista.
# Para ampliar o escopo basta adicionar operadores aqui.
OPERADORES_ATIVOS: list[str] = [
    "ezequiel.nunes",
    "raul.araujo",
    "kaua.chagas",
    "igor.chiva",
]

# ── Tipos de movimentação (coluna origem) ─────────────────────────────────────
ORIGENS: dict[str, str] = {
    "SD1": "Entrada",
    "SD2": "Saída",
    "SD3": "Movimentação Interna",
}

# ── Setores que NÃO entram em rankings de produção ────────────────────────────
_EXCLUIDOS_DA_PRODUCAO = {"expedicao"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_label_setor(setor: str) -> str:
    return SETORES.get(setor, {}).get("label", setor.capitalize())


def get_setor_de(operador: str) -> str | None:
    """Retorna o setor de um operador, ou None se não cadastrado."""
    for setor, dados in SETORES.items():
        if operador.lower() in dados["operadores"]:
            return setor
    return None


def get_operadores_setor(setor: str) -> list[str]:
    """Retorna lista de operadores de um setor (aceita variações de nome)."""
    chave = _normalizar_setor(setor)
    return list(SETORES.get(chave, {}).get("operadores", []))


def get_excluidos_producao() -> list[str]:
    """Retorna todos os operadores que NÃO devem entrar em rankings de produção."""
    excluidos = []
    for setor in _EXCLUIDOS_DA_PRODUCAO:
        excluidos.extend(SETORES.get(setor, {}).get("operadores", []))
    return excluidos


def todos_operadores() -> list[str]:
    """Retorna todos os operadores cadastrados em qualquer setor."""
    return [op for dados in SETORES.values() for op in dados["operadores"]]


def _normalizar_setor(setor: str) -> str:
    aliases = {
        "producao": "producao",
        "produção": "producao",
        "expedicao": "expedicao",
        "expedição": "expedicao",
        "expedicão": "expedicao",
        "revisao": "revisao",
        "revisão": "revisao",
    }
    return aliases.get(setor.lower().strip(), setor.lower().strip())
