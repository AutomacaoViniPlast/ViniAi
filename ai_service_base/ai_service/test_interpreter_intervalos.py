from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.interpreter import RuleBasedInterpreter, _periodo_from_text


def main() -> int:
    interp = RuleBasedInterpreter()

    cases = [
        (
            "E do dia 01/04 até 06/04 ?",
            ("01/04/2026", "06/04/2026", "01/04/2026 até 06/04/2026"),
            ("clarify", "clarify"),
        ),
        (
            "Qual a produção total do dia 01/04 até o dia 06/04 ?",
            ("01/04/2026", "06/04/2026", "01/04/2026 até 06/04/2026"),
            ("total_fabrica", "sql"),
        ),
        (
            "Qual a produção total no dia 1 de abril?",
            ("01/04/2026", "01/04/2026", "dia 01/04/2026"),
            ("total_fabrica", "sql"),
        ),
        (
            "Qual a produção total dia a dia de 01/04 até 08/04",
            ("01/04/2026", "08/04/2026", "01/04/2026 até 08/04/2026"),
            ("producao_por_dia", "sql"),
        ),
    ]

    failed = False
    for message, expected_periodo, expected_intent_route in cases:
        periodo = _periodo_from_text(message)
        ir = interp.interpret(message)
        ok = periodo == expected_periodo and (ir.intent, ir.route) == expected_intent_route
        status = "[OK]" if ok else "[FAIL]"
        print(
            f"{status} {message} -> periodo={periodo} intent={ir.intent} route={ir.route}"
        )
        if not ok:
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
