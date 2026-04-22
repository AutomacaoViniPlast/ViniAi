# RAG Conversacional

## O que é

"RAG" (Retrieval-Augmented Generation) no ViniAI é **conversacional**: em vez de recuperar documentos externos, o sistema recupera o **intent e contexto das mensagens anteriores** para enriquecer a interpretação da mensagem atual.

Não há documentos ou embeddings — os dados vêm do banco SQL e o contexto vem do histórico de conversa.

---

## Os Três Mecanismos

### 1. Context Carry-over (RAG puro)

**Quando ativa:**
- `route` da mensagem atual = `clarify` ou `smalltalk`
- `confidence` < 0.75
- A mensagem atual contém um período explícito

**O que faz:**
Varre o histórico em ordem reversa, encontra a última mensagem SQL completa (> 3 palavras) e reutiliza o intent dela com o novo período.

**Exemplo:**
```
Turno 1 — user:      "Qual foi o LD do Ezequiel nesse mês?"
Turno 1 — assistant: [dados de LD]

Turno 2 — user:      "Quero saber de janeiro!"
           ↓ interpreter: clarify, conf=0.40, período=janeiro
           ↓ orchestrator: conf < 0.75 + período → RAG carry-over
              └─ herda intent "geracao_ld_por_operador" + entity="ezequiel.nunes"
              └─ substitui período → janeiro
           ↓ SQL executado corretamente ✓
```

**Refinamento — combinação de entidade:**
Se entre a mensagem completa e a atual houver uma mensagem curta com nome de operador (ex: "Ezequiel"), essa entidade é usada no intent herdado.

---

### 2. Period Inherit

**Quando ativa:**
- `route` = `sql` (intent já identificado com clareza)
- Nenhum período explícito na mensagem atual
- `confidence` < 0.87

**O que faz:**
Varre as últimas 6 mensagens do usuário em ordem reversa e herda o período da primeira que continha uma referência temporal explícita.

**Exemplo:**
```
Turno 1 — user:      "Qual o LD do Ezequiel em janeiro?"
Turno 1 — assistant: [tabela]

Turno 2 — user:      "E o do Igor?"
           ↓ interpreter: geracao_ld_por_operador, entity=igor.chiva, período=None
           ↓ SEM period-inherit: usaria mês atual (errado)
           ↓ COM period-inherit: herda "janeiro" do turno 1 ✓
```

---

### 3. Recurso Carry-over (Caso 3)

**Quando ativa:**
- `route` = `sql`, `intent` = `producao_por_operador`
- `entity_value` = None (nenhum operador identificado)
- `confidence` < 0.75
- A mensagem atual menciona extrusora/recurso (ex: "E na extrusora 2?")

**O que faz:**
Detecta que a mensagem é um follow-up de extrusora sem operador, varre o histórico em busca do último intent SQL completo, herda esse intent e substitui o campo `recursos` pelo novo recurso detectado na mensagem atual.

**Exemplo:**
```
Turno 1 — user:      "Qual a produção total na extrusora 1 em março?"
Turno 1 — assistant: [dados MAC1]

Turno 2 — user:      "E na extrusora 2?"
           ↓ interpreter: producao_por_operador, conf=0.60, entity=None, recursos=["0007"]
           ↓ orchestrator: Caso 3 → recurso carry-over
              └─ herda intent anterior (ex: "total_fabrica" ou "producao_por_operador")
              └─ substitui recursos=["0007"]
           ↓ SQL executado com MAC2 ✓
```

---

### 4. Auto-inject de Operador

**Quando ativa:**
- `intent` in (`geracao_ld_por_operador`, `producao_por_operador`)
- `entity_value` = None (nenhum operador foi extraído do texto)

**O que faz:**
Mapeia o nome do usuário autenticado (`user_name` do payload) para um login de operador cadastrado e injeta como `entity_value`.

**Mapeamento:**
- `"Ezequiel Nunes"` → `"ezequiel.nunes"`
- `"igor"` → `"igor.chiva"` (busca por primeiro nome)
- `"Pedro Martins"` → `None` (não é operador cadastrado)

**Consequência para não-operadores:** `entity_value` permanece `None` → mensagem de clarificação solicitando o nome.

---

## Comparação dos Mecanismos

| | Carry-over (1) | Period Inherit (2) | Recurso Carry-over (3) | Auto-inject (4) |
|---|---|---|---|---|
| **Trigger** | clarify/smalltalk + conf<0.75 + período na msg | sql + sem período + conf<0.87 | sql + prod_por_operador + entity=None + conf<0.75 + recurso na msg | entity_value=None + intent de operador |
| **O que herda** | Intent completo + período | Só o período | Intent completo + substitui recurso | Entidade (operador) |
| **Lookback** | Todo o histórico (32 msgs) | Últimas 6 mensagens do usuário | Todo o histórico (32 msgs) | Não usa histórico — usa payload |

---

## Histórico de Conversa

- Lido por `context_manager.py` → PostgreSQL N8N, tabela `mensagens`
- Limite: **32 mensagens** por request (configurado no orchestrator)
- Somente leitura — quem grava é o Backend Node.js
- Stateless por design: nenhum estado em memória do FastAPI

---

## Âncora Temporal (LLM)

Toda chamada ao ChatGPT injeta a data atual no topo do system prompt:

```
**Data de hoje:** 16/04/2026 (quinta-feira)
Use essa data como referência absoluta para "hoje", "este mês", etc.
NUNCA invente ou assuma datas sem usar este valor.
```

Isso elimina alucinação temporal — o ChatGPT sabia responder perguntas mas não sabia que dia era hoje.

---

## Contexto do Usuário no LLM

Quando a rota é `smalltalk` ou `clarify`, o orchestrator injeta no system prompt:

```
## Usuário atual
- Nome: [user_name]
- Departamento: [user_setor]
- Cargo: [user_cargo]
```

Isso permite à Ayla saudar pelo nome e personalizar a conversa ao contexto do departamento.

---

## Links relacionados

- [[Interpretacao-de-Intencao]] — classifica a mensagem antes do RAG
- [[PostgreSQL]] — onde o histórico é armazenado
- [[Agentes]] — system prompt e contexto de cada agente
