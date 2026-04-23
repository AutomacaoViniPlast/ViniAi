from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.interpreter import RuleBasedInterpreter


def main() -> int:
    interp = RuleBasedInterpreter()

    cases = [
        ("Qual a produção da extrusora?", "comparativo_extrusoras"),
        ("Qual o valor de cada MAC?", "comparativo_extrusoras"),
        ("Qual o valor total de cada MAC na produção desse mes?", "comparativo_extrusoras"),
        ("Qual a produção exata por Extrusora?", "comparativo_extrusoras"),
        ("Qual a soma desses valores?", "total_fabrica"),
    ]

    failed = False
    for message, expected_intent in cases:
        ir = interp.interpret(message)
        ok = ir.intent == expected_intent and ir.route == "sql"
        status = "[OK]" if ok else "[FAIL]"
        print(f"{status} {message} -> intent={ir.intent}, route={ir.route}")
        if not ok:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
