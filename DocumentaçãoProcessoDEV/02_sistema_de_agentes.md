# ViniAI — Sistema de Agentes

**Versão:** 1.0  
**Última atualização:** Abril/2026

---

## O que é um Agente

Cada agente é uma IA especializada em um departamento da Viniplast. Ele tem:

- **Nome próprio** (ex: Ayla)
- **Domínio de dados** (ex: Produção)
- **Personalidade** definida via system prompt enviado ao ChatGPT
- **Texto de capacidades** exibido quando o usuário pergunta "o que você faz?"

Os agentes são registrados centralmente em `app/agents.py`.

---

## Agentes Cadastrados

| ID | Nome | Departamento | Status |
|----|------|-------------|--------|
| `producao` | **Ayla** | Produção (inclui Revisão e Expedição) | Ativo |
| `pcp` | **Iris** | PCP — Planejamento e Controle de Produção | Futuro |
| `controladoria` | **Maya** | Controladoria / Custos | Futuro |
| `pesagem` | **Lara** | Pesagem de Bobinas | Futuro |
| `rh` | **Nina** | Recursos Humanos | Futuro |
| `vendas` | **Eva** | Vendas e Clientes | Futuro |
| `qualidade` | **Luna** | Controle de Qualidade | Futuro |
| `logistica` | **Vera** | Logística e Expedição | Futuro |

---

## Ayla — Agente de Produção (Ativo)

### Domínio
Ayla responde consultas sobre dados de produção da fábrica, extraídos da view `v_kardex_ld` no banco METABASE.

### O que ela sabe responder

**LD (Material com Defeito — Revisão de Qualidade)**
- Quem gerou mais LD em determinado período
- Ranking de produtos com mais LD
- Total de LD por operador específico

**Produção Geral**
- Ranking de produção por operador
- Produção por turno
- Produção por produto específico
- Total geral da fábrica

**Setores e Operadores**
- Listar operadores da revisão ou expedição
- Filtrar rankings por setor

**Períodos**
- Qualquer mês/ano desde Jul/2019
- Atalhos: "este mês", "mês passado", "este ano", "ano passado"

### Operadores Cadastrados

| Setor | Operadores |
|-------|-----------|
| Revisão | raul.araujo, igor.chiva, ezequiel.nunes |
| Expedição | john.moraes, rafael.paiva, andre.prado, richard.santos, arilson.aguiar |
| Produção | kaua.chagas (outros em cadastramento) |

> **Importante:** A Ayla atende **toda** a área de Produção — Extrusora, Pesagem, Qualidade e Expedição
> são sub-setores cobertos por ela. Não há agentes separados por sub-setor por enquanto.
> Um único perfil `producao` no frontend dá acesso a todos esses dados via Ayla.

### Conversa Natural
A Ayla usa o **ChatGPT (gpt-4o-mini)** para responder:
- Saudações e conversa casual
- Perguntas gerais sobre a fábrica
- Mensagens que não foram identificadas como consultas de dados

Para consultas de dados (produção, LD, rankings), ela usa **SQL direto** no banco — sem custo de LLM.

---

## Como Adicionar um Novo Agente

### 1. Registrar em `agents.py`

```python
"novo_setor": {
    "name": "NomeDoAgente",
    "domain": "Departamento",
    "description": "Breve descrição do que o agente faz.",
    "system_prompt": """
        Você é o/a NomeDoAgente, assistente de [departamento] da Viniplast.
        [Definir personalidade, domínio e regras de resposta]
    """,
    "capabilities": """
        ### O que o/a NomeDoAgente consegue responder
        [Listar exemplos de perguntas que o agente responde]
    """,
},
```

### 2. Configurar permissões em `permissions.py`

```python
_AGENTES_POR_PERFIL = {
    ...
    "novo_setor": {"novo_setor"},  # usuários desse perfil acessam apenas esse agente
}
```

### 3. Criar endpoint (se necessário) em `main.py`

Se o agente tiver seu próprio endpoint, instanciar o orquestrador com o `agent_id` correto:

```python
orchestrator_novo = ChatOrchestrator(agent_id="novo_setor")
```

---

## Fluxo de Decisão do Agente

```
Mensagem recebida
       │
       ▼
RuleBasedInterpreter (sem LLM — rápido)
       │
       ├─► Consulta de dados (SQL) ──► SQLService ──► Banco METABASE
       │
       ├─► Conversa natural / Não identificado ──► ChatGPT (OpenAI)
       │
       └─► "O que você faz?" ──► Texto de capabilities do agents.py
```
