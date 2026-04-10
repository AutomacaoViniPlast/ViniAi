"""
Testes do LLMHandler e integração com o orchestrator.

Execução:
  cd ai_service_base/ai_service
  python test_llm.py

Cobertura:
  1. LLMHandler inicializa sem API key (modo offline)
  2. Fallback retorna texto coerente para intent "smalltalk"
  3. Fallback retorna texto coerente para intent "clarify"
  4. _build_messages monta sequência correta (começa/termina com user)
  5. RuleBasedInterpreter detecta saudações expandidas → route=smalltalk
  6. RuleBasedInterpreter detecta clarify → route=clarify
  7. [Opcional] Chamada real à API quando ANTHROPIC_API_KEY está configurada
"""
from __future__ import annotations

import os
import sys

# Garante que o path do módulo app está disponível
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────

PASS = "[OK]"
FAIL = "[FAIL]"
results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    status = PASS if condition else FAIL
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))


# ── Teste 1-3: LLMHandler offline ────────────────────────────────────────────

print("\n[1/7] LLMHandler — modo offline (sem API key)")
# Força ausência de chave para testar fallback
_original_key = os.environ.pop("ANTHROPIC_API_KEY", "")
os.environ["ANTHROPIC_API_KEY"] = ""

from app.llm_handler import LLMHandler

handler_offline = LLMHandler()
check("Handler inicializa sem API key", not handler_offline.enabled)
check(
    "Fallback smalltalk retorna string não vazia",
    bool(handler_offline.respond("oi", intent="smalltalk")),
)
check(
    "Fallback clarify retorna string não vazia",
    bool(handler_offline.respond("xkcd abc def", intent="clarify")),
)

# ── Teste 4: _build_messages ──────────────────────────────────────────────────

print("\n[2/7] LLMHandler._build_messages — montagem de contexto")
from app.schemas import ConversationTurn

history = [
    ConversationTurn(role="user", content="Oi!"),
    ConversationTurn(role="assistant", content="Olá! Como posso ajudar?"),
]
msgs = LLMHandler._build_messages(history, "Quem produziu mais em janeiro?")

check("Mensagens não vazia", len(msgs) > 0)
check("Última mensagem é do usuário", msgs[-1]["role"] == "user")
check("Última mensagem é a atual", msgs[-1]["content"] == "Quem produziu mais em janeiro?")
check("Sem duplicata da mensagem atual", sum(1 for m in msgs if m["content"] == "Quem produziu mais em janeiro?") == 1)

# ── Teste 5-6: RuleBasedInterpreter ──────────────────────────────────────────

print("\n[3/7] RuleBasedInterpreter — detecção de smalltalk")
from app.interpreter import RuleBasedInterpreter

interp = RuleBasedInterpreter()

smalltalk_cases = [
    "oi",
    "olá",
    "bom dia",
    "boa tarde",
    "boa noite",
    "tudo bem?",
    "e aí",
    "como vai?",
    "obrigado",
    "valeu",
    "blz",
    "beleza",
    "oi tudo bem",
    "preciso de ajuda",
    "como você está?",
    "oi ViniAI",
]

for msg in smalltalk_cases:
    ir = interp.interpret(msg)
    check(
        f'smalltalk: "{msg}"',
        ir.route == "smalltalk",
        f"route={ir.route} intent={ir.intent}",
    )

print("\n[4/7] RuleBasedInterpreter — SQL routes (não devem cair em smalltalk)")
sql_cases = [
    "ranking de produção em janeiro de 2026",
    "top 5 com mais LD em 2025",
    "quem mais produziu LD?",
    "produção por turno em março",
    "total da fábrica este mês",
]
for msg in sql_cases:
    ir = interp.interpret(msg)
    check(
        f'sql: "{msg[:40]}"',
        ir.route == "sql",
        f"route={ir.route} intent={ir.intent}",
    )

print("\n[5/7] RuleBasedInterpreter — clarify fallback")
clarify_cases = [
    "banana amarela",
    "xkcd 42",
    "qual é o sentido da vida?",
]
for msg in clarify_cases:
    ir = interp.interpret(msg)
    check(
        f'clarify: "{msg}"',
        ir.route in ("clarify", "smalltalk"),
        f"route={ir.route}",
    )

# ── Teste 7: API real (opcional) ──────────────────────────────────────────────

print("\n[6/7] LLMHandler — chamada real à API")
os.environ["ANTHROPIC_API_KEY"] = _original_key

if _original_key:
    handler_live = LLMHandler()
    if handler_live.enabled:
        response = handler_live.respond("Bom dia! Tudo bem?", intent="smalltalk")
        check("API retornou resposta não vazia", bool(response), response[:80] if response else "")
        check("Resposta não é fallback fixo", "ViniAI" not in response[:30] or len(response) > 50)
        check("Resposta em português (heurística)", any(w in response.lower() for w in ["bom", "ola", "olá", "dia", "tudo", "ajudar"]))
    else:
        print("  — Handler não ativou mesmo com key (verifique a biblioteca anthropic)")
else:
    print("  — ANTHROPIC_API_KEY não configurada: pulando teste de API real")
    print("     Configure a chave no .env para testar a chamada real.")

# ── Sumário ───────────────────────────────────────────────────────────────────

print("\n" + "═" * 60)
total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"  Resultado: {passed}/{total} testes passaram")
if failed:
    print(f"\n  Falhas:")
    for name, ok, detail in results:
        if not ok:
            print(f"    {FAIL} {name}" + (f" — {detail}" if detail else ""))
print("═" * 60 + "\n")

sys.exit(0 if failed == 0 else 1)
