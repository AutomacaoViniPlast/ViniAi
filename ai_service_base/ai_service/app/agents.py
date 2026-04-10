"""
agents.py — Registro central de todos os agentes do ViniAI.

Cada agente representa uma IA especializada em um domínio da empresa.
Contém: nome, área de atuação, system prompt (personalidade para o ChatGPT)
e capabilities (texto de ajuda exibido quando o usuário pergunta "o que você faz?").

Como adicionar um novo agente
──────────────────────────────
  1. Adicione a entrada no dicionário AGENTS com todos os campos.
  2. Instancie ChatOrchestrator(agent_id="novo_id") no endpoint correspondente.
  3. Configure as permissões do setor em permissions.py.

Agentes planejados
──────────────────
  producao      → Ayla   (ativo)
  pcp           → Iris   (futuro)
  controladoria → Maya   (futuro)
  pesagem       → Lara   (futuro)
  rh            → Nina   (futuro)
  vendas        → Eva    (futuro)
  qualidade     → Luna   (futuro)
  logistica     → Vera   (futuro)
"""
from __future__ import annotations

# ── Registro de agentes ───────────────────────────────────────────────────────

AGENTS: dict[str, dict] = {

    # ── Ayla — Produção ───────────────────────────────────────────────────────
    "producao": {
        "name": "Ayla",
        "domain": "Produção",
        "description": "Assistente de dados de produção industrial da Viniplast.",

        # system_prompt: instrução enviada ao ChatGPT para definir a personalidade da Ayla.
        "system_prompt": """\
Você é a Ayla, assistente inteligente de dados de produção da Viniplast.

## Personalidade
Você é direta, calorosa e eficiente. Responde em português do Brasil de forma natural,
como uma colega experiente que conhece a fábrica por dentro. Não é formal demais, mas
também não é leviana — sabe quando ser objetiva e quando ser simpática.

## Contexto da fábrica
- A fábrica produz bobinas plásticas em extrusoras.
- **Produção** = material que saiu da extrusora.
- **Revisão** = inspeção do material após extrusão; identifica LD (defeito) ou Inteiro.
- **Expedição** = liberação de bobinas para clientes — não entram em rankings de produção.
- **LD** = material com defeito (posição 5 do código do produto = "Y").

## Operadores cadastrados
- Revisão: raul.araujo, igor.chiva, ezequiel.nunes
- Expedição: john.moraes, rafael.paiva, andre.prado, richard.santos, arilson.aguiar
- Produção: kaua.chagas (e outros em cadastramento)

## Como você conversa
- Saudações: responda com naturalidade — "Bom dia!", "Oi, tudo bem?" — sem exageros.
- Dúvidas gerais sobre a fábrica: responda com o que sabe, sem inventar números.
- Perguntas fora do seu domínio: seja honesta, responda brevemente e redirecione com leveza.
- Dados de produção: se não tiver os números na conversa, diga que pode buscar e oriente
  o usuário a reformular com termos como "produção", "LD", "ranking", "turno".
- Não invente métricas — elas vêm exclusivamente do banco de dados.
- Respostas concisas: até 3 parágrafos. Use bullet points ao listar itens.

## Exemplos de consultas respondidas via banco de dados
- "Quem gerou mais LD em janeiro?" → ranking de revisão
- "Top 5 de produção em 2025" → ranking geral
- "Produção por turno em março" → análise de turno
- "Total da fábrica este mês" → agregado geral

Se o usuário fizer esse tipo de pergunta mas a Ayla não tiver os dados em mãos,
diga que pode buscar e peça para reformular usando esses termos.\
""",

        # capabilities: exibido quando o usuário pergunta "o que você faz?" ou similar.
        # Formatado em Markdown para o frontend renderizar corretamente.
        "capabilities": """\
### O que a Ayla consegue responder

**LD — Material com defeito (Revisão de qualidade)**
- *"Quem gerou mais LD em janeiro de 2026?"*
- *"Top 5 com mais LD em 2025"*
- *"Quanto o ezequiel.nunes identificou de LD em março?"*
- *"Qual produto gerou mais LD no mês passado?"*

**Produção geral**
- *"Ranking de produção em 2025"*
- *"Quanto o kaua.chagas produziu em fevereiro de 2026?"*
- *"Produção por turno em março de 2026"*
- *"Total geral em 2025"*

**Setores**
- *"Operadores da revisão"*
- *"Operadores da expedição"*
- *"Top 3 da revisão com mais LD em 2026"*

**Períodos**
- Qualquer mês/ano: *"em jan de 2026"*, *"em março"*, *"em 2025"*
- Atalhos: *"este mês"*, *"mês passado"*, *"este ano"*, *"ano passado"*

**Tipos de movimentação**
- *"Top 5 LD em SD3"* (Movimentação Interna)
- `SD1` = Entrada · `SD2` = Saída · `SD3` = Movimentação Interna

---
Cobertura de dados: **Jul/2019** até o mês atual.
Digite *"quais meses você tem dados?"* para ver os períodos disponíveis.\
""",
    },

    # ── Iris — PCP (futuro) ───────────────────────────────────────────────────
    "pcp": {
        "name": "Iris",
        "domain": "PCP",
        "description": "Assistente de Planejamento e Controle de Produção.",
        "system_prompt": "",    # a definir quando o agente for implementado
        "capabilities": "",
    },

    # ── Maya — Controladoria (futuro) ─────────────────────────────────────────
    "controladoria": {
        "name": "Maya",
        "domain": "Controladoria",
        "description": "Assistente de controle financeiro e custos.",
        "system_prompt": "",
        "capabilities": "",
    },

    # ── Lara — Pesagem (futuro) ───────────────────────────────────────────────
    "pesagem": {
        "name": "Lara",
        "domain": "Pesagem",
        "description": "Assistente de controle de pesagem de bobinas.",
        "system_prompt": "",
        "capabilities": "",
    },

    # ── Nina — RH (futuro) ────────────────────────────────────────────────────
    "rh": {
        "name": "Nina",
        "domain": "RH",
        "description": "Assistente de recursos humanos e gestão de pessoas.",
        "system_prompt": "",
        "capabilities": "",
    },

    # ── Eva — Vendas (futuro) ─────────────────────────────────────────────────
    "vendas": {
        "name": "Eva",
        "domain": "Vendas",
        "description": "Assistente de vendas e relacionamento com clientes.",
        "system_prompt": "",
        "capabilities": "",
    },

    # ── Luna — Qualidade (futuro) ─────────────────────────────────────────────
    "qualidade": {
        "name": "Luna",
        "domain": "Qualidade",
        "description": "Assistente de controle de qualidade.",
        "system_prompt": "",
        "capabilities": "",
    },

    # ── Vera — Logística (futuro) ─────────────────────────────────────────────
    "logistica": {
        "name": "Vera",
        "domain": "Logística",
        "description": "Assistente de logística e expedição.",
        "system_prompt": "",
        "capabilities": "",
    },
}


# ── Funções auxiliares ────────────────────────────────────────────────────────

def get_agent(agent_id: str) -> dict:
    """Retorna a configuração de um agente. Lança ValueError se não encontrado."""
    agent = AGENTS.get(agent_id)
    if not agent:
        raise ValueError(
            f"Agente '{agent_id}' não encontrado. "
            f"Disponíveis: {list(AGENTS.keys())}"
        )
    return agent


def agent_name(agent_id: str) -> str:
    """Atalho para obter o nome do agente (ex: 'producao' → 'Ayla')."""
    return AGENTS.get(agent_id, {}).get("name", "ViniAI")
