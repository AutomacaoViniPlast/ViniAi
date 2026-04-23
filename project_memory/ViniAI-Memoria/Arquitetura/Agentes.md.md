# Agentes

## O que é um Agente

Cada agente é uma IA especializada em um departamento da Viniplast. Ele possui:

- **Nome próprio** com personalidade definida
- **Domínio de dados** exclusivo
- **System prompt** enviado ao ChatGPT para definir o comportamento
- **Capabilities** — texto exibido quando o usuário pergunta "o que você faz?"

Os agentes são registrados em `app/agents.py` e instanciados no `app/orchestrator.py`.

---

## Estado Atual

| Nome | ID | Departamento | Status | Cobre |
|------|----|-------------|--------|-------|
| **Ayla** | `producao` | Produção | **Ativo** | Extrusora, Revisão/Qualidade |
| Iris | `pcp` | PCP | Futuro | Planejamento e Controle de Produção |
| Maya | `controladoria` | Controladoria | Futuro | Financeiro e Custos |
| Nina | `rh` | RH | Futuro | Recursos Humanos |
| Eva | `vendas` | Vendas | Futuro | Comercial e Clientes |
| Lara | `pesagem` | — | Nome reservado | Coberto pela Ayla |
| Luna | `qualidade` | — | Nome reservado | Coberto pela Ayla |
| Vera | `logistica` | — | Nome reservado | Coberto pela Ayla |

---

## Ayla — Assistente de Produção

### Escopo

A Ayla atende **Extrusora e Revisão/Qualidade**:

| Sub-setor | O que responde | Base |
|-----------|---------------|------|
| Extrusora | Produção de bobinas, KG, KGH, m/min, rankings por peso | SH6 |
| Qualidade / Revisão | Inteiro, LD, Fora de Padrão — por operador, período ou total | V_KARDEX |

### Operadores Cadastrados

> Fonte da verdade: `app/config.py`

| Setor | ID config | Operadores | Dados via |
|-------|-----------|-----------|-----------|
| Extrusora | `extrusora` | celio.divino, aramis.leal, valdenrique.silva, andreson.reis, ednilson.soares, nobrega.valter, gilmar.santos | SH6 |
| Revisão | `revisao` | kaua.chagas, ezequiel.nunes, igor.chiva, raul.ribeiro | V_KARDEX |

**`OPERADORES_ATIVOS`** = `OPERADORES_EXTRUSORA` + `OPERADORES_REVISAO` (todos os listados acima)

**Regra de roteamento por setor:**
- Operador em `extrusora` → query vai para SH6 (produção de bobinas)
- Operador em `revisao` → query vai para V_KARDEX (qualidade, LD, Inteiro, FP)
- Operador desconhecido → ignorado por enquanto

> [!note] kaua.chagas
> Setor "produção" na empresa, mas operacionalmente atua na revisão. Listado em `revisao` no `config.py`.

### Personalidade (resumo do system_prompt)

- Direta, calorosa e eficiente — como uma colega que conhece a fábrica
- Em saudações: responde o cumprimento + oferece ajuda de forma natural e variada
- Explica conceitos (LD, revisão, turno, expedição) de forma acessível
- Nunca inventa dados — todos vêm do banco SQL
- Nunca começa resposta com "Claro!" ou "Certamente!" — varia as aberturas
- Usa a data injetada como referência absoluta para períodos relativos
- Guard de dados: se a mensagem contém LD/produção/expedição → busca no banco, não conversa
- Quando a pergunta vier ambígua, conduz o usuário para a estrutura:
  **métrica + recorte + período**
- Ensina sintaxe recomendada em exemplos concretos como:
  - "Qual foi a produção total da fábrica em abril de 2026?"
  - "Qual o valor total de cada MAC em abril de 2026?"
  - "Quanto o igor.chiva produziu em abril de 2026?"
  - "Quanto de LD o ezequiel.nunes identificou em abril de 2026?"
- Não assume operador, máquina ou período quando isso altera o resultado.
- Quando o usuário pergunta capacidades, a resposta fixa deve sair em primeira pessoa,
  como a própria Ayla, e não como um texto sobre a Ayla em terceira pessoa.
- Quando perguntarem sobre cobertura temporal, a Ayla deve responder com os períodos
  reais das bases que ela consulta, em vez de texto estático.
- Os filtros de revisão usados pela Ayla para perguntas de LD e qualidade devem incluir
  todos os revisores válidos do fluxo atual, incluindo `raul.ribeiro`,
  para não truncar rankings ou totais da `V_KARDEX`.

### Rotas de resposta

| Tipo de mensagem | Rota | Handler |
|-----------------|------|---------|
| Saudações, explicações, dúvidas | `smalltalk` | ChatGPT (gpt-4o-mini) |
| Mensagem não identificada | `clarify` | ChatGPT com orientação |
| "O que a Ayla faz?" | `tipos_informacao` | Texto fixo de capabilities |
| Qualquer consulta de dados | `sql` | SQL Server direto |

---

## Como Adicionar um Novo Agente

1. **`app/agents.py`** — adicionar entrada com `name`, `domain`, `system_prompt`, `capabilities`
2. **`app/permissions.py`** — adicionar mapeamento `departamento → agent_id`
3. **`app/main.py`** — instanciar `ChatOrchestrator(agent_id="novo_id")` + novo endpoint
4. Atualizar este vault e o `CLAUDE.md`

---

## Links relacionados

- [[Arquitetura-Geral]] — onde os agentes se encaixam no sistema
- [[Interpretacao-de-Intencao]] — como as mensagens são classificadas
- [[RAG-Conversacional]] — como o contexto é mantido entre mensagens
- [[Pendencias]] — backlog de novos agentes
