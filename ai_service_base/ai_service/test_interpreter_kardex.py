from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.interpreter import RuleBasedInterpreter


def main() -> int:
    interp = RuleBasedInterpreter()

    cases = [
        ("Qual o total de LD gerado ontem?", "ld_total", "sql"),
        ("Qual foi a geracao de LD nesse mes?", "ld_total", "sql"),
        ("Quanto de LD o ezequiel.nunes identificou esse mes?", "geracao_ld_por_operador", "sql"),
        ("Producao de ontem por qualidade", "resumo_qualidade", "sql"),
        ("Quanto foi inteiro, LD e fora de padrao ontem?", "resumo_qualidade", "sql"),
    ]

    failed = False
    for message, expected_intent, expected_route in cases:
        ir = interp.interpret(message)
        ok = ir.intent == expected_intent and ir.route == expected_route
        status = "[OK]" if ok else "[FAIL]"
        print(f"{status} {message} -> intent={ir.intent}, route={ir.route}")
        if not ok:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
