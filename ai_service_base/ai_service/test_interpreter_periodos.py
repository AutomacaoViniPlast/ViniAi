from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.interpreter import RuleBasedInterpreter


def main() -> int:
    interp = RuleBasedInterpreter()

    cases = [
        ("Quais meses voce tem dados de producao?", "periodos_disponiveis", "producao"),
        ("Quais meses voce tem dados de qualidade?", "periodos_disponiveis", "qualidade"),
        ("Quais meses voce tem dados de revisao?", "periodos_disponiveis", "revisao"),
        ("Quais periodos disponiveis de revisão?", "periodos_disponiveis", "revisao"),
        ("Quais meses voce tem dados?", "periodos_disponiveis", None),
    ]

    failed = False
    for message, expected_intent, expected_metric in cases:
        ir = interp.interpret(message)
        ok = ir.intent == expected_intent and ir.metric == expected_metric and ir.route == "sql"
        status = "[OK]" if ok else "[FAIL]"
        print(f"{status} {message} -> intent={ir.intent}, metric={ir.metric}, route={ir.route}")
        if not ok:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
