# ViniAI — RAG Conversacional, Contexto e Interpretador

**Versão:** 3.2  
**Última atualização:** Abril/2026  
**Responsável técnico:** TI / Desenvolvimento

---

## 1. O Problema que Este Módulo Resolve

### v2.0 — Falhas resolvidas anteriormente

| Sintoma | Causa raiz |
|---------|-----------|
| "Qual foi o LD produzido **nesse mês**?" → perguntava o operador | `"nesse mês"` não era reconhecido como período |
| Usuário autenticado precisava dizer o próprio nome | Sem auto-inject do login do usuário |
| "Quero saber **desse mês**!" → Ayla reiniciava a conversa | Sem RAG: mensagem ambígua ia para LLM sem contexto |

### v3.0 — Falhas resolvidas nesta versão

| Sintoma | Causa raiz | Correção |
|---------|-----------|----------|
| LLM respondia com datas inventadas / ano errado | `llm_handler.py` não injetava `date.today()` no system prompt | Data atual injetada dinamicamente em cada chamada LLM |
| "E o do Igor?" após consulta de janeiro usava mês atual | Herança de período não ocorria em follow-ups SQL claros | Novo mecanismo `period-inherit` no orchestrator |
| Contexto perdido em conversas longas | Histórico limitado a 8 mensagens | Aumentado para 12 mensagens |
| Agente sem âncora temporal no system prompt | `agents.py` sem instrução sobre uso de datas | Adicionada seção "Regras de data e tempo" |

---

## 2. Fluxo Completo de Processamento (v2.0)

```
Mensagem do usuário
      │
      ▼
[interpreter.py] interpret(message)
      │
      ├─ Extrai período (hoje / nesse mês / semana passada / jan 2026 / etc.)
      ├─ Extrai operador (nome.sobrenome ou primeiro nome)
      ├─ Classifica intent (22 regras em ordem de prioridade)
      └─ Retorna InterpretationResult { intent, route, confidence, ... }
      │
      ▼
[orchestrator.py] process(payload)
      │
      ├─ 1. Lê histórico (últimas 16 mensagens do banco N8N)
      ├─ 2. Resolve user_name / user_setor / user_cargo do payload
      ├─ 3. Chama interpreter.interpret(message)
      ├─ 4. Verifica permissão LGPD
      │
      ├─ 5. RAG CONVERSACIONAL (Caso 1) ◄── v2.0
      │      Se route=clarify/smalltalk + confiança < 75% + período detectado:
      │      └─ _try_context_followup(recent, novo_período)
      │           ├─ Varre histórico: extrai operador de mensagens curtas
      │           ├─ Encontra último intent SQL completo (> 3 palavras)
      │           ├─ Substitui período → novo período
      │           └─ Retorna intent reutilizado → vai para SQL (não LLM)
      │
      ├─ 5b. HERANÇA DE PERÍODO (Caso 2) ◄── v3.0 NOVO
      │      Se route=sql + sem período explícito na msg + confiança < 87%:
      │      └─ _inherit_period_from_history(recent)
      │           ├─ Varre msgs do usuário (mais recente → mais antiga)
      │           ├─ Encontra a primeira que continha período explícito
      │           └─ Aplica esse período na IR atual → evita usar mês atual errado
      │
      ├─ 6. AUTO-INJECT DE OPERADOR ◄── v2.0
      │      Se intent = geracao_ld_por_operador ou producao_por_operador
      │      E entity_value = None:
      │      └─ _user_login_from_name(user_name) → injeta login do usuário
      │
      └─ 7. Roteia: SQL ou LLM
            LLM recebe data atual no topo do system prompt ◄── v3.0 NOVO
```

---

## 3. RAG Conversacional — Como Funciona

### O que é

"RAG" (Retrieval-Augmented Generation) neste contexto significa usar o **histórico de conversa** como fonte de recuperação para enriquecer a interpretação da mensagem atual.

No ViniAI, não há documentos externos — os dados vêm do banco SQL. O RAG aqui é **conversacional**: recupera o intent anterior para resolver mensagens ambíguas.

### Algoritmo de Context Carry-over

```python
def _try_context_followup(recent, ini_new, fim_new, lbl_new):
    user_msgs = [t.content for t in reversed(recent) if t.role == "user"]

    # Passo 1: extrai operador de mensagens curtas (ex: "Ezequiel")
    entity_override = None
    for msg in user_msgs:
        if len(msg.split()) <= 3:
            op = interpreter._extract_operator(msg)
            if op:
                entity_override = op
                break

    # Passo 2: busca último intent SQL completo (> 3 palavras)
    for msg in user_msgs:
        if len(msg.split()) <= 3:
            continue  # pula clarificações curtas

        prev_ir = interpreter.interpret(msg)
        if prev_ir.route == "sql" and prev_ir.confidence >= 0.55:
            # Combina: entidade da clarificação + intent da mensagem completa
            if entity_override and not prev_ir.entity_value:
                prev_ir.entity_value = entity_override
            # Substitui o período
            prev_ir.data_inicio = ini_new or prev_ir.data_inicio
            prev_ir.data_fim    = fim_new or prev_ir.data_fim
            prev_ir.period_text = lbl_new or prev_ir.period_text
            return prev_ir  # ← reutiliza intent com novo período

    return None  # nenhum contexto encontrado → vai para LLM
```

### Exemplo Concreto

```
Turno 1 — user:      "Qual foi o LD produzido nesse mês?"
Turno 1 — assistant: "Nenhum LD identificado por ezequiel.nunes em Abril de 2026."
            ↑ (Ayla estava pedindo o operador antes — agora auto-injeta)

Turno 2 — user:      "Ezequiel"
Turno 2 — assistant: "### LD identificado em revisão
                       Operador: ezequiel.nunes (Revisão)
                       Período: Abril de 2026
                       Total: 1.234,56 KG"

Turno 3 — user:      "Quero saber desse mês!"
           ↓ interpreter: intent=clarify, conf=0.40, período=Abril 2026
           ↓ orchestrator: conf < 0.75 + período extraído → RAG carry-over
              ├─ user_msgs reversas: ["Ezequiel", "Qual foi o LD..."]
              ├─ "Ezequiel" (curta) → entity_override = "ezequiel.nunes"
              ├─ "Qual foi o LD produzido nesse mês?" → intent=geracao_ld_por_operador
              └─ aplica entity="ezequiel.nunes" + período=Abril 2026
           ↓ SQL executado → resposta correta ✓
```

---

## 3b. Herança de Período — Period Inherit (v3.0)

### O problema que resolve

Quando o usuário faz um follow-up de entidade sem repetir o período:

```
Turno 1 — user:      "Qual o LD do Ezequiel em janeiro?"
Turno 1 — assistant: [tabela com dados de janeiro]

Turno 2 — user:      "E o do Igor?"
           ↓ interpreter: intent=geracao_ld_por_operador, entity=igor.chiva
                          período: NÃO mencionado → _default_periodo() = Abril/2026 ← ERRADO
           ↓ ANTES v3.0: consultava Abril/2026 em vez de janeiro
           ↓ DEPOIS v3.0: herda janeiro do histórico → consulta correta ✓
```

### Quando ativa

- `ir.route == "sql"` (o interpreter já identificou o intent com clareza)
- Nenhum período explícito na mensagem atual (`_periodo_from_text(msg)` retorna `None`)
- `ir.confidence < 0.87` (para não sobrescrever queries completas e autossuficientes)

### Algoritmo

```python
def _inherit_period_from_history(recent, max_lookback=6):
    user_msgs = [t.content for t in reversed(recent) if t.role == "user"]
    for msg in user_msgs[:max_lookback]:  # até 6 msgs atrás
        ini, fim, lbl = _periodo_from_text(msg)
        if ini and fim:
            return ini, fim, lbl  # ← usa o período mais recente encontrado
    return None  # ← não encontrou: usa o default (mês atual)
```

### Diferença entre Caso 1 (RAG carry-over) e Caso 2 (Period Inherit)

| | Caso 1 — RAG carry-over | Caso 2 — Period Inherit |
|---|---|---|
| **Trigger** | route=clarify/smalltalk + conf<0.75 + período na msg | route=sql + sem período na msg + conf<0.87 |
| **O que herda** | Intent + período (o intent vem do histórico) | Só o período (o intent já foi identificado) |
| **Exemplo** | "Quero saber de janeiro!" (intent não claro) | "E o do Igor?" (intent claro, período não dito) |

---

## 4. Auto-inject de Operador

### Problema resolvido

Usuário autenticado pergunta *"Qual o meu LD nesse mês?"* — a IA não deve pedir o nome de quem já está logado.

### Como funciona

```python
# Em orchestrator.py, após a interpretação do intent:
if intent in ("geracao_ld_por_operador", "producao_por_operador") and entity_value is None:
    user_login = _user_login_from_name(user_name)
    if user_login:
        ir.entity_value = user_login  # injeta automaticamente
```

```python
# _user_login_from_name() em orchestrator.py:
def _user_login_from_name(user_name):
    # Se já for login: "ezequiel.nunes" → retorna direto
    if "." in user_name and user_name.lower() in todos_operadores():
        return user_name.lower()

    # Busca pelo primeiro nome: "Ezequiel Nunes" → "ezequiel.nunes"
    for operador in todos_operadores():
        primeiro_nome = operador.split(".")[0]
        if re.search(rf"\b{primeiro_nome}\b", user_name, re.IGNORECASE):
            return operador

    return None  # não é operador cadastrado
```

**Consequência**: usuários que não são operadores (ex: gerência, TI) terão `entity_value=None` após o auto-inject, e a mensagem de clarificação será exibida normalmente.

---

## 5. Períodos Suportados (interpreter.py)

### Períodos simples

| Expressão no texto | Período resolvido |
|-------------------|------------------|
| `hoje` | Data de hoje |
| `ontem` | Data de ontem |
| `esta semana`, `nessa semana` | Segunda a domingo da semana atual |
| `semana passada` | Segunda a domingo da semana anterior |
| `últimos 7 dias`, `últimos 30 dias` | Rolling: hoje − N dias até hoje |
| `mês passado`, `mês anterior` | Primeiro ao último dia do mês anterior |
| `este mês`, `nesse mês`, `desse mês`, `esse mês` | Mês atual (dinâmico) |
| `este ano`, `esse ano`, `nesse ano` | Ano atual |
| `ano passado` | Ano anterior completo |
| `janeiro`, `fevereiro`... | Mês do ano atual |
| `janeiro de 2026`, `jan/2026` | Mês específico |
| `2025`, `em 2025` | Ano completo |
| *(nenhum)* | **Mês atual** (antes: `01/01/2025 a 31/12/2026`) |

> **Importante**: o período padrão mudou de um intervalo fixo de 2 anos para o **mês atual dinâmico**. Isso evita que uma pergunta sem período retorne anos de dados irrelevantes.

### Intervalos entre períodos (v3.1 — novo)

Expressões que definem um **range de meses** são resolvidas automaticamente pelo `_try_parse_range()`, com prioridade máxima na função `_periodo_from_text()`.

| Expressão | Período resolvido | Padrão |
|-----------|------------------|--------|
| `de agosto de 2025 até hoje` | 01/08/2025 → hoje | `de X até Y` |
| `desde março de 2025 até abril de 2026` | 01/03/2025 → 30/04/2026 | `desde X até Y` |
| `de janeiro até este mês` | 01/01/[ano] → último dia do mês atual | `de X até Y` |
| `de agosto a dezembro de 2025` | 01/08/2025 → 31/12/2025 | `de X a Y` |
| `entre agosto de 2025 e hoje` | 01/08/2025 → hoje | `entre X e Y` |
| `entre janeiro e março` | 01/01/[ano] → 31/03/[ano] | `entre X e Y` |

**Como funciona internamente:**

```python
# _try_parse_range separa o texto em dois endpoints
# ex: "de agosto de 2025 até hoje"
#     ini_txt = "agosto de 2025"   → _parse_endpoint(ini_txt, as_start=True)  → "01/08/2025"
#     fim_txt = "hoje"             → _parse_endpoint(fim_txt, as_start=False) → "13/04/2026"

# _parse_endpoint reconhece: hoje, ontem, este mês, mês passado, este ano,
#   ano passado, "agosto de 2025", "agosto 2025", "agosto", "2025"
```

**Separadores reconhecidos (em ordem de prioridade):**
1. `até` / `ate` — unambiguous, highest priority
2. `entre...e` — "entre agosto e hoje"
3. `a` — somente quando Y começa com mês nomeado, "hoje", "ontem" ou ano (evita falsos positivos)

---

## 6. Intents Suportados e Variantes de Pergunta

### `geracao_ld_por_operador` — LD de um operador
```
"Qual foi o LD do ezequiel em janeiro?"
"Quanto de LD a raul.araujo identificou esse mês?"
"LD do Igor no mês passado"
"Meu LD nesse mês"            ← primeira pessoa (auto-inject)
"Quanto eu identifiquei de LD?"
"LD em abril"                  ← usa usuário autenticado
```

### `ranking_usuarios_ld` — Quem gerou mais LD
```
"Quem gerou mais LD em janeiro?"
"Top 5 com mais LD em 2025"
"Ranking de LD da revisão esse mês"
"Quem tem mais LD? Top 3"
"Qual o líder de LD em março?"
"Quem se destacou em LD?"
```

### `ranking_produtos_ld` — Produto com mais LD
```
"Qual produto gerou mais LD?"
"Top 5 de produtos com mais defeito"
"Qual material tem mais LD em 2025?"
"Ranking de produtos com LD no mês passado"
```

### `producao_por_operador` — Produção de um operador
```
"Quanto o kaua.chagas produziu em fevereiro?"
"Produção do Raul em 2025"
"Minha produção nesse mês"     ← primeira pessoa
"Quanto eu produzi essa semana?"
"Quanto foi expedido pelo john.moraes?"
```

### `ranking_producao_geral` — Ranking de produção
```
"Ranking de produção em 2025"
"Top 5 de produção esse mês"
"Quem mais produziu no mês passado?"
"Qual o maior produtor em 2026?"
"Quem se destacou na produção?"
```

### `producao_por_turno` — Por turno
```
"Produção por turno em março"
"Quanto cada turno produziu nesse mês?"
"Produção dos turnos em 2025"
```

### `total_fabrica` — Total geral
```
"Total da fábrica em janeiro"
"Resultado geral em 2026"
"Visão geral de produção esse mês"
"Quanto foi produzido no total?"
```

### `periodos_disponiveis` — Cobertura temporal
```
"Quais meses você tem dados?"
"Histórico disponível"
"Desde quando tem dados?"
"Até que data tenho informação?"
```

### `list_operadores_revisao` — Lista de operadores
```
"Quais são os operadores da revisão?"
"Liste os revisores"
"Quem faz parte da expedição?"
"Mostre os operadores"
```

---

## 7. Prioridade das Regras de Interpretação

As regras são avaliadas em ordem. Regras com maior especificidade vêm primeiro:

```
 1. tipos_informacao    — "o que a Ayla faz?" / "o que você consegue?" (padrão restrito)
 2. periodos_disponiveis — "quais meses tem?"
 3. smalltalk (curto)   — saudações ≤ 8 palavras (lista expandida: despedidas, variações)
 4. smalltalk (longo)   — conversa natural  ⚠️ com guard: se a mensagem contém
                          LD / PRODUCAO / EXPEDICAO, deixa cair para SQL rules
 ── [extração de entidades: período, operador, produto, setor] ──
 5. list_operadores     — "quais operadores da revisão?"
 6. ranking_produtos_ld — LD + produto + qual/ranking/top
 7. ranking_usuarios_ld — LD + ranking/top/quem
 8. LD próprio          — LD + "meu/minha/eu identifiquei"
 9. LD por operador     — LD + ação ou operador explícito
10. LD genérico         — LD sem operador → usa autenticado
11. ranking prod + quem — PRODUCAO + quem/ranking/top
12. ranking geral       — ranking/top sem LD
13. prod por produto    — código de produto + produção
14. prod por turno      — palavra "turno"
15. total fábrica       — "total", "geral", "visão geral"
16. prod própria        — PRODUCAO + "meu/minha/eu produzi"
17. expedição           — "expedido", "liberado", "enviado"
18. prod por operador   — PRODUCAO ou operador explícito
19. clarify (fallback)  — nada identificado → LLM explica
```

### Guard da regra 4 (smalltalk_longa)

A regra 4 verifica explicitamente antes de ativar:

```python
_tem_dado = self._LD.search(low) or self._PRODUCAO.search(low) or self._EXPEDICAO.search(low)
if self._SMALLTALK_LONGA.search(low) and not _tem_dado:
    # → smalltalk
```

Isso garante que frases como *"me fale sobre o LD de janeiro"* ou
*"pode me dizer quanto o Igor produziu?"* caiam nas regras SQL (9 e 18),
e não sejam respondidas como conversa pelo ChatGPT.

---

## 8. Como Aperfeiçoar o Sistema

### 8.1 Adicionar Novas Variantes de Pergunta

Edite `app/interpreter.py`, na classe `RuleBasedInterpreter`:

```python
# Exemplo: adicionar "bobinagem" como sinônimo de produção
_PRODUCAO = re.compile(
    r"produ[cç][aã]o|produziu|...|bobinagem|bobinou",  # ← adicionar aqui
    re.IGNORECASE,
)
```

Regras:
- Use `|` para separar alternativas no regex
- Prefira `\b` (word boundary) para evitar falsos positivos
- Use `re.IGNORECASE` em todas as regras
- Teste com `python -c "from app.interpreter import RuleBasedInterpreter; ..."`

### 8.2 Adicionar Novos Períodos

Edite `_periodo_from_text()` em `interpreter.py`:

```python
# Exemplo: "próxima semana" (período futuro)
_RE_PROX_SEMANA = re.compile(r"pr[oó]xima\s+semana", re.IGNORECASE)

if _RE_PROX_SEMANA.search(lowered):
    inicio = today + timedelta(days=7 - today.weekday())
    fim    = inicio + timedelta(days=6)
    return inicio.strftime("%d/%m/%Y"), fim.strftime("%d/%m/%Y"), "próxima semana"
```

### 8.3 Adicionar Novos Intents

1. Adicione o padrão no `interpret()` respeitando a ordem de prioridade
2. Adicione o handler no `_dispatch()` do orchestrator
3. Se necessário, adicione uma nova query em `sql_service.py`
4. Atualize as `capabilities` em `agents.py`

### 8.4 Ajustar o RAG Conversacional

O carry-over é ativado quando:
- `route` = `clarify` ou `smalltalk`
- `confidence` < `0.75`
- Um período é detectado na mensagem atual

Para ajustar o threshold de ativação:
```python
# orchestrator.py, método process()
if ir.route in ("clarify", "smalltalk") and ir.confidence < 0.75:  # ← ajustar aqui
```

Para ajustar o threshold mínimo de confiança para reutilização de intent:
```python
# orchestrator.py, método _try_context_followup()
if prev_ir.route == "sql" and prev_ir.confidence >= 0.55:  # ← ajustar aqui
```

### 8.5 Adicionar Novos Operadores

Edite apenas `app/config.py`:

```python
SETORES = {
    "revisao": {
        "operadores": [
            "raul.araujo",
            "igor.chiva",
            "ezequiel.nunes",
            "novo.operador",  # ← adicionar aqui
        ],
    },
    ...
}
```

O `todos_operadores()` é chamado dinamicamente — o auto-inject e o `_extract_operator` se atualizam automaticamente.

---

## 9. Arquitetura de Armazenamento de Contexto

```
Frontend (WhatsApp / Web)
    │
    ▼
Backend Node.js
    │─── Salva mensagem user    ──► banco N8N (tabela mensagens)
    │─── Chama POST /v1/chat/process
    │
    ▼
FastAPI (ai_service)
    │
    ├─ context_manager.py ──► lê últimas 16 msgs do banco N8N (somente leitura)
    │   SELECT role, conteudo FROM mensagens WHERE conversa_id = %s
    │   ORDER BY criado_em DESC LIMIT 16
    │
    ├─ RAG carry-over (em memória, não persistido)
    │   Funciona sobre o histórico já lido — sem armazenamento extra
    │
    └─ Salva resposta assistant ──► Node.js é responsável por isso
```

> **Nota de design**: o contexto do orchestrator é **stateless** — cada request é independente. O estado da conversa vive no banco N8N, não na memória do serviço. Isso permite escalar o FastAPI horizontalmente sem problemas.

---

## 10. Limitações Conhecidas e Próximos Passos

### Limitações atuais

| Limitação | Impacto | Prioridade |
|-----------|---------|-----------|
| RAG carry-over usa re-interpretação (não persiste o intent resolvido) | Pode errar em conversas complexas | Média |
| `_extract_operator` aceita logins desconhecidos sem validação | Pode fazer query sem resultados | Baixa |
| Sem suporte a "comparação entre períodos" | "Janeiro vs Fevereiro" não funciona | Alta |
| Período padrão = mês atual (pode surpreender quem quer período amplo) | Query retorna só o mês corrente | Baixa |
| Period-inherit pode herdar período antigo se usuário mudou de assunto | Poucos casos — confiança < 0.87 mitiga | Baixa |

### Corrigido na v3.0

| Limitação (resolvida) | Como foi corrigido |
|----------------------|-------------------|
| LLM alucina datas / responde com ano errado | Data real injetada no system prompt via `llm_handler.py` |
| Follow-up de entidade ("E o do Igor?") usava mês atual | `_inherit_period_from_history()` em `orchestrator.py` |
| Histórico curto (8 msgs) causava perda de contexto | Aumentado para 16 mensagens |

### Corrigido na v3.1

| Limitação (resolvida) | Como foi corrigido |
|----------------------|-------------------|
| "de agosto de 2025 até hoje" retornava só "hoje" | `_try_parse_range()` + `_parse_endpoint()` em `interpreter.py` |
| "entre agosto e dezembro" não era reconhecido | Padrão `entre X e Y` adicionado ao `_try_parse_range()` |
| "de agosto a dezembro de 2025" não era reconhecido | Padrão `de X a Y` com validação de endpoint adicionado |

### Corrigido na v3.2

| Limitação (resolvida) | Como foi corrigido |
|----------------------|-------------------|
| Ayla respondia saudações de forma fria / sem oferecer ajuda | `system_prompt` reescrito com instruções explícitas para saudações proativas e variadas |
| `_SMALLTALK_LONGA` interceptava consultas de dados como *"me fale sobre o LD de janeiro"* | Guard adicionado à regra 4: não ativa se `_LD / _PRODUCAO / _EXPEDICAO` presentes |
| `_CAPACIDADES` muito ampla (`ajuda`, `pode me dizer`) capturava perguntas erradas | Padrão restrito a consultas explícitas sobre capacidades da Ayla |
| Saudações como "até logo", "bom fds", variações com "Ayla" não eram reconhecidas | `_SMALLTALK` expandido com despedidas e variantes de nome |
| `boa[!.]*$` no regex causava conflito com `\b` no fechamento do grupo | Corrigido para `boa\b` |

### Próximos passos sugeridos

1. **Persistir intent resolvido no banco**: salvar o último `InterpretationResult` resolvido por `session_id` para o carry-over ser 100% preciso, sem re-interpretação.

2. **Comparação entre períodos**: novo intent `comparacao_periodos` + query SQL com dois ranges de data.

3. **Substituição do interpretador por LLM fine-tuned**: o `RuleBasedInterpreter` pode ser substituído por uma chamada estruturada ao Claude/GPT com function calling, mantendo a mesma interface `InterpretationResult`. As regras atuais servem como exemplos de treinamento.

4. **Suporte a material I (Inteiro)**: quando a extrusora começar a ter operadores cadastrados, adicionar intent `producao_inteiro` e filtro `SUBSTRING(produto, 5, 1) = 'I'`.

5. **Feedback loop**: registrar no banco quais intents foram `[context-carry]` e quais tiveram `confidence < 0.6` para identificar os padrões que mais falham.

---

## 11. Referências de Código

| Arquivo | Responsabilidade |
|---------|-----------------|
| `app/interpreter.py` | Parsing de períodos, regex de intent, 22 regras de classificação |
| `app/orchestrator.py` | RAG carry-over, auto-inject de operador, roteamento SQL/LLM |
| `app/context_manager.py` | Leitura do histórico do banco N8N (somente leitura) |
| `app/sql_service.py` | Queries SQL — fonte dos dados |
| `app/config.py` | Operadores cadastrados — fonte da verdade |
| `app/agents.py` | System prompt da Ayla + capabilities |
