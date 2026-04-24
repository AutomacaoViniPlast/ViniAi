from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.config import OPERADORES_EXTRUSORA, OPERADORES_REVISAO, get_setor_de


def main() -> int:
    casos = [
        ("nobrega.valter", "extrusora"),
        ("gilmar.santos", "extrusora"),
        ("raul.ribeiro", "revisao"),
    ]

    failed = False
    for operador, setor_esperado in casos:
        setor = get_setor_de(operador)
        esta_na_lista = (
            operador in OPERADORES_REVISAO
            if setor_esperado == "revisao"
            else operador in OPERADORES_EXTRUSORA
        )
        ok = setor == setor_esperado and esta_na_lista
        status = "[OK]" if ok else "[FAIL]"
        print(f"{status} {operador} -> setor={setor}")
        if not ok:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
