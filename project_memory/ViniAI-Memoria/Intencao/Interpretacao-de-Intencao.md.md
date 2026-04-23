# Interpretação de Intenção

## Visão Geral

O `RuleBasedInterpreter` (`app/interpreter.py`) classifica cada mensagem em uma **intenção** e uma **rota** usando **regras de regex**, sem qualquer chamada a LLM.

**Por que regras em vez de LLM?**
- Determinístico — sempre produz o mesmo resultado para a mesma entrada
- Instantâneo — sem latência de API
- Sem custo de tokens para as consultas mais frequentes
- Fácil de auditar e corrigir

O resultado é um `InterpretationResult` com: `intent`, `route`, `confidence`, `data_inicio`, `data_fim`, `entity_value`, `top_n`, `setor`, `origem`, `recursos`.

---

## Rotas Possíveis

| Rota | Handler | Quando |
|------|---------|--------|
| `sql` | SQLServiceSH6 / SQLServiceKardex → SQL Server | Consulta de dados identificada com clareza |
| `smalltalk` | ChatGPT (LLMHandler) | Saudações, perguntas conceituais, conversa natural |
| `clarify` | ChatGPT (LLMHandler) | Nenhuma intenção identificada — orienta o usuário |

---

## Ordem de Prioridade das Regras

```
 1.  tipos_informacao         → "o que a Ayla faz?", "o que você consegue?"
 2.  periodos_disponiveis     → "quais meses tem dados?", "desde quando?"
 3.  smalltalk (curto)        → saudações ≤ 8 palavras
 4.  smalltalk (longo)        → conversa natural
                                ⚠️ Guard: se contém LD/produção/expedição → cai para SQL
 ── extração de entidades: período, operador, produto, setor, origem, recurso ──
 5.  list_operadores          → "quais operadores da revisão?"
 6.  ranking_produtos_ld      → LD + produto + qual/ranking/top
 7.  ranking_usuarios_ld      → LD + ranking/top/quem
 8.  LD próprio               → LD + "meu/minha/eu identifiquei"
 9.  geracao_ld_por_operador  → LD + ação de geração ou operador explícito
 9b. geracao_ld_por_operador  → LD genérico sem operador → usa usuário autenticado
10a. comparativo_extrusoras   → comparar/versus/vs + extrusoras, produção + extrusora,
                                "cada MAC", "cada máquina", "produção exata por extrusora"
10b. horas_trabalhadas        → "horas trabalhadas", "total de horas", "quantas horas"
11a. metros_por_minuto        → "metros por minuto", "m/min", "velocidade da máquina"
11b. kgh                      → "kgh", "kg/h", "kg por hora", "produtividade em kg"
12.  ranking_producao_geral   → produção + quem/ranking/top
13.  ranking_producao_geral   → ranking/top sem LD nem produção específica
14.  producao_por_produto     → código de produto + produção
15.  producao_por_turno       → palavra "turno"
16.  total_fabrica            → "total", "geral", "visão geral"
17.  producao_por_operador    → produção própria ("meu/minha/eu produzi")
18.  producao_por_operador    → expedição ("expedido", "liberado", "bobinas liberadas")
19.  producao_por_operador    → produção com operador explícito ou padrão
20.  clarify (fallback)       → nada identificado com segurança
```

---

## Guard da Regra 4

A regra de smalltalk longa tem uma proteção explícita:

> Se a mensagem contiver LD, produção ou expedição junto com qualquer padrão conversacional,
> ela não é tratada como conversa — cai para as regras SQL.

Exemplos que **não** vão ao LLM por causa do guard:
- *"me fale sobre o LD de janeiro"* → regra 9 (LD por operador)
- *"pode me dizer quanto o Igor produziu?"* → regra 19 (prod por operador)
- *"me explica quanto foi expedido nesse mês"* → regra 18 (expedição)

---

## Extração de Recurso (_extract_recurso)

Campo `recursos` no `InterpretationResult` — lista de strings com os recursos detectados.

| Expressão | Resultado |
|-----------|-----------|
| "extrusora 1", "mac 1", "máquina 1", "0003" | `["0003"]` |
| "extrusora 2", "mac 2", "máquina 2", "0007" | `["0007"]` |
| "revisão" (sem mencionar extrusora/produção) | `["0005", "0006"]` |
| Não mencionado | `None` → usa padrão `("0003", "0007")` |

### Regras conversacionais importantes para extrusoras

- Perguntas genéricas como *"qual a produção da extrusora?"*, *"qual o valor de cada MAC?"* e
  *"qual o valor total de cada MAC na produção desse mês?"* agora devem cair em
  `comparativo_extrusoras`, não em `total_fabrica`.
- Quando a frase menciona `extrusora`, `máquina` ou `MAC` sem número explícito, o interpretador
  assume comparação/detalhamento das duas extrusoras produtivas (`0003` e `0007`).
- Follow-ups como *"qual a soma desses valores?"* são tratados como `total_fabrica`, permitindo
  ao orchestrator herdar o período do contexto anterior e consolidar os valores exibidos por MAC.

---

## Períodos Suportados

### Simples

| Expressão | Período resolvido |
|-----------|------------------|
| `hoje` | Data de hoje |
| `ontem` | Data de ontem |
| `esta semana`, `essa semana` | Seg–Dom da semana atual |
| `semana passada` | Seg–Dom da semana anterior |
| `últimos N dias` | Rolling: hoje − N dias |
| `mês passado`, `mês anterior` | Primeiro ao último dia do mês anterior |
| `este mês`, `nesse mês`, `desse mês` | Mês atual dinâmico |
| `este ano`, `esse ano` | Ano atual |
| `ano passado` | Ano anterior completo |
| `janeiro`, `fevereiro`... | Mês do ano atual |
| `janeiro de 2026`, `jan 2026` | Mês específico |
| `2025`, `em 2025` | Ano completo |
| *(nenhum mencionado)* | **Mês atual** (default dinâmico) |

### Intervalos

| Expressão | Exemplo |
|-----------|---------|
| `de X até Y` | "de agosto de 2025 até hoje" |
| `desde X até Y` | "desde março até abril de 2026" |
| `entre X e Y` | "entre agosto e dezembro de 2025" |
| `de X a Y` | "de agosto a dezembro de 2025" |

---

## Extração de Entidades

| Entidade | Como extrai |
|----------|------------|
| Operador | Padrão `nome.sobrenome` ou primeiro nome contra lista de `todos_operadores()` |
| Produto | Código alfanumérico de produto (ex: CLI..., TD2...) |
| Top N | `top 5`, `top 3`, `5 operadores` |
| Setor | Palavras "expedição", "revisão", "produção" → normalizado via `config.py` |
| Origem | `SD1`/`SD2`/`SD3` ou "entrada"/"saída"/"interna" |
| Recurso | "extrusora 1/2", "mac 1/2", "máquina 1/2", "0003"/"0007" → `_extract_recurso()` |

---

## Níveis de Confiança

| Faixa | Significado |
|-------|------------|
| ≥ 0.90 | Intent claro e explícito |
| 0.80–0.89 | Intent provável mas com ambiguidade |
| 0.60–0.79 | Intent inferido com incerteza |
| < 0.60 | Fallback — vai para LLM |

Os limiares `0.75` e `0.87` são usados pelo orchestrator para ativar RAG carry-over e period-inherit respectivamente.

---

## Como Ampliar

### Novo padrão de frase
Editar os regex no topo da classe `RuleBasedInterpreter` (ex: `_PRODUCAO`, `_LD`, `_SMALLTALK`).

### Novo intent
1. Adicionar verificação no método `interpret()` respeitando a ordem de prioridade
2. Adicionar handler correspondente em `orchestrator._dispatch()`
3. Criar método em `sql_service_sh6.py` ou `sql_service_kardex.py` conforme o caso

### Novo período
Adicionar padrão em `_periodo_from_text()` seguindo o padrão existente.

---

## Links relacionados

- [[RAG-Conversacional]] — o que acontece após a classificação
- [[Agentes]] — quem usa o interpretador
- [[SQLServer]] — destino das consultas SQL
