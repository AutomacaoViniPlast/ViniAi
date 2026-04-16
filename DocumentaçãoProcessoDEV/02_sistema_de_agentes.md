# ViniAI — Sistema de Agentes

**Versão:** 1.4  
**Última atualização:** Abril/2026

---

## O que é um Agente

Cada agente é uma IA especializada em um departamento da Viniplast. Ele tem:

- **Nome próprio** (ex: Ayla)
- **Departamento** que atende (ex: Produção)
- **Personalidade** definida via system prompt enviado ao ChatGPT
- **Texto de capacidades** exibido quando o usuário pergunta *"o que você faz?"*

Os agentes são registrados centralmente em `app/agents.py`.

---

## Estado Atual dos Agentes

| Nome | ID | Departamento | Sub-setores atendidos | Status |
|------|----|--------------|-----------------------|--------|
| **Ayla** | `producao` | Produção | Extrusora, Pesagem, Qualidade, Expedição | **Ativo** |
| **Iris** | `pcp` | PCP | — | Futuro |
| **Maya** | `controladoria` | Controladoria | — | Futuro |
| **Nina** | `rh` | RH | — | Futuro |
| **Eva** | `vendas` | Vendas | — | Futuro |
| Lara | `pesagem` | — | Coberto pela Ayla | Nome reservado |
| Luna | `qualidade` | — | Coberto pela Ayla | Nome reservado |
| Vera | `logistica` | — | Coberto pela Ayla | Nome reservado |

> **Lara, Luna e Vera** são nomes reservados para eventual especialização futura.
> Enquanto isso, a **Ayla** cobre todos esses sub-setores.

---

## Ayla — Assistente de Produção (Ativo)

### Escopo
A Ayla é a assistente de **toda a área de Produção**. Ela atende os seguintes sub-setores sem necessidade de agentes separados:

| Sub-setor | O que cobre |
|-----------|------------|
| **Extrusora** | Produção de bobinas — volume gerado, rankings de operadores, turnos |
| **Pesagem** | Controle de peso das bobinas produzidas |
| **Qualidade / Revisão** | Inspeção do material — identificação de LD (defeito) ou Inteiro |
| **Expedição** | Liberação de bobinas para clientes — movimentação de material |

### O que ela responde

**Qualidade / LD — Material com Defeito**
- Quem gerou mais LD em determinado período
- Ranking de produtos com mais LD
- Total de LD por operador específico

**Produção — Extrusora**
- Ranking de produção por operador
- Produção por turno
- Produção por produto específico
- Total geral da fábrica

**Expedição**
- Operadores da expedição e seus volumes
- Movimentação de bobinas no período

**Geral**
- Listar operadores por sub-setor
- Períodos disponíveis no banco (Jul/2019 até hoje)
- Conversa natural via ChatGPT para dúvidas gerais

### Operadores Cadastrados

> **Fonte da verdade:** `app/config.py` — qualquer alteração deve ser feita apenas lá.

| Sub-setor | Setor (config.py) | Operadores |
|-----------|-------------------|-----------|
| Qualidade/Revisão | `revisao` | raul.araujo, igor.chiva, ezequiel.nunes |
| Expedição | `expedicao` | john.moraes, rafael.paiva, andre.prado, richard.santos, arilson.aguiar |
| Extrusora/Produção | `producao` | *(em cadastramento — lista vazia no config.py)* |

**`OPERADORES_ATIVOS`** (escopo padrão de consultas sem setor explícito):
`ezequiel.nunes`, `raul.araujo`, `kaua.chagas`, `igor.chiva`

> **Nota:** `kaua.chagas` está em `OPERADORES_ATIVOS` mas ainda não foi adicionado ao setor `producao` em `SETORES`. Para incluí-lo completamente, adicionar `"kaua.chagas"` na lista `operadores` do setor `producao` em `config.py`.

### Conversa Natural (v1.4)
Para mensagens que não são consultas de dados, a Ayla usa o **ChatGPT (gpt-4o-mini)**:

- Saudações e despedidas — responde o cumprimento + oferece ajuda de forma natural e variada
- Explicações conceituais — "o que é LD?", "como funciona a revisão?", "o que é turno?"
- Dúvidas gerais sobre a fábrica
- Feedback e agradecimentos
- Mensagens não identificadas como consulta

**Guard de dados:** se a mensagem contém LD/produção/expedição, vai para SQL mesmo que
pareça conversacional — ex: *"me fale sobre o LD de janeiro"* → SQL, não ChatGPT.

Para dados (produção, LD, rankings), usa **SQL direto no banco** — sem custo de LLM.

---

## Como Adicionar um Novo Agente

### 1. Registrar em `app/agents.py`

```python
"id_do_agente": {
    "name": "NomeDoAgente",
    "domain": "Departamento",
    "description": "Breve descrição.",
    "system_prompt": """
        Você é o/a NomeDoAgente, assistente de [departamento] da Viniplast.
        [Personalidade, domínio, regras de resposta]
    """,
    "capabilities": """
        ### O que o/a NomeDoAgente consegue responder
        [Exemplos de perguntas]
    """,
},
```

### 2. Configurar permissões em `app/permissions.py`

```python
_AGENTES_POR_DEPARTAMENTO = {
    ...
    "novo_departamento": {"id_do_agente"},
}
```

### 3. Criar endpoint em `app/main.py` (se necessário)

```python
orchestrator_novo = ChatOrchestrator(agent_id="id_do_agente")

@app.post("/v1/novo_agente/process")
def process_novo(payload: ChatProcessRequest):
    return orchestrator_novo.process(payload)
```

### 4. Documentar

Atualizar este arquivo e `03_controle_acesso_lgpd.md`.

---

## Fluxo de Decisão do Agente

```
Mensagem recebida (com user_setor, user_name, session_id)
           │
           ▼
  Lê histórico: 16 msgs (context_manager → banco N8N)
           │
           ▼
   Verifica permissão LGPD
   (permissions.py)
           │
    ┌──────┴──────┐
   Negado       Permitido
    │               │
    ▼               ▼
Mensagem      RuleBasedInterpreter
LGPD          (classifica 19 regras, sem LLM)
              extrai: período, operador, setor, top_n
                    │
                    ▼
         intent = tipos_informacao?
          │          │
         Sim        Não
          │          │
          ▼          ▼
    capabilities   RAG Conversacional
    (agents.py)        │
                  ┌────┴──────────────────┐
                  │                       │
            Caso 1: clarify/smalltalk  Caso 2: sql sem
            + conf<0.75 + período      período explícito
                  │                + conf<0.87
            herda intent SQL do         │
            histórico (carry-over)  herda período da
                  │                última msg c/ data
                  └────────┬──────────────┘
                           │
                           ▼
                  Auto-inject de operador
                  (entity=None + user logado)
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
         sql route                smalltalk/clarify
              │                         │
              ▼                         ▼
        SQLService               ChatGPT (OpenAI)
      (SQL Server          + data atual no system prompt
       STG_KARDEX)
```
