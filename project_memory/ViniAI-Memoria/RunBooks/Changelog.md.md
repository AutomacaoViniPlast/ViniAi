# Changelog de Sessoes

> Gerado automaticamente pelo hook Stop do Claude Code via `scripts/sync_memory.py`.
> Cada entrada representa uma sessao de desenvolvimento com arquivos alterados.

---

## 2026-04-17
- `CLAUDE.md`

## 2026-04-20
- `CLAUDE.md`

## 2026-04-22
- `ai_service_base/ai_service/app/sql_service_kardex.py`

## 2026-04-23

### Validação com 20 perguntas — bugs encontrados e corrigidos

**`app/config.py`**
- Atualização de operadores: extrusora agora tem 7 operadores (celio.divino, aramis.leal, valdenrique.silva, andreson.reis, ednilson.soares, nobrega.valter, gilmar.santos); revisão tem 4 (kaua.chagas, ezequiel.nunes, igor.chiva, raul.ribeiro)
- Adicionado `get_setor_de()` helper e reestruturação dos setores

**`app/interpreter.py`**
- **Fix `_PRODUTO`**: regex agora usa `\bprodutos?\b` e `\bmateriais?\b` (plural + singular). Antes `\bproduto\b` não capturava "produtos" → queries de "quais produtos tiveram mais LD" caíam em `ld_total` em vez de `ranking_produtos_ld`
- **Fix `_COMPARATIVO`**: removido match singular `produ[cç][aã]o\s+da\s+extrusora`. Agora só plural (`das extrusoras`, `das máquinas`, `dos macs`) força comparativo. "Produção da Extrusora 1" agora mantém `recursos=["0003"]` corretamente
- **Fix encoding**: `reasoning` com caracteres garbled (`ProduÃ§Ã£o`) corrigido para ASCII
- `_extract_setor()`: adicionado "extrusora" ao loop de aliases

**`app/orchestrator.py`**
- Import ampliado: `OPERADORES_EXTRUSORA`, `OPERADORES_REVISAO`, `get_setor_de`
- Auto-inject (seção 4d) agora valida setor antes de injetar operador autenticado
- `geracao_ld_por_operador`: se operador for de extrusora → retorna mensagem de redirecionamento
- `producao_por_operador`: se operador for de revisão → chama `kardex.get_resumo_qualidade()` em vez de SH6
- `resumo_qualidade`: removido `filtro_usuarios=OPERADORES_REVISAO` — Inteiro (QUALIDADE='I') é registrado por operadores de extrusora, não revisores; filtro excluía todos os registros de Inteiro

**`app/sql_service_kardex.py`**
- `get_resumo_qualidade()`: removido filtro `LOCAL_OP=EXTRUSAO` — dados de qualidade (Inteiro/LD/FP) têm LOCAL_OP variável, não só EXTRUSAO

- `CLAUDE.md`

## 2026-04-24
- `CLAUDE.md`
- `PLANILHA_VALIDACAO_IA.md`
