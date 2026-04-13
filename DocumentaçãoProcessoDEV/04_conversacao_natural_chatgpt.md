# ViniAI — Conversação Natural com ChatGPT

**Versão:** 1.1  
**Última atualização:** Abril/2026

---

## Visão Geral

O sistema usa o **ChatGPT (OpenAI)** para responder mensagens que não são
consultas de dados — saudações, perguntas gerais, dúvidas sobre a fábrica,
e qualquer mensagem que o interpretador de regras não conseguiu classificar.

---

## Quando o ChatGPT é Acionado

| Situação | Exemplo | Rota |
|----------|---------|------|
| Saudações e conversa casual | "Bom dia!", "tudo bem?", "obrigado" | `smalltalk` → ChatGPT |
| Pergunta geral sobre a fábrica | "O que é LD?", "me explica revisão" | `smalltalk` → ChatGPT |
| Mensagem não identificada | "banana amarela", texto sem contexto | `clarify` → ChatGPT |
| Consulta de dados de produção | "quem produziu mais LD em janeiro?" | `sql` → Banco direto |
| "O que você faz?" | "quais suas capacidades?" | `tipos_informacao` → texto fixo |

> **Importante:** Consultas de dados vão **direto ao banco SQL**, sem passar pelo ChatGPT.
> Isso garante rapidez, precisão e sem custo de tokens para as perguntas mais frequentes.

---

## Modelo Utilizado

- **Modelo padrão:** `gpt-4o-mini` — rápido, barato, ideal para conversa
- **Alternativas:** `gpt-4o`, `gpt-4-turbo` (mais potentes, maior custo)
- **Configuração:** variável `OPENAI_MODEL` no arquivo `.env`

---

## Contexto de Conversa

O ChatGPT recebe as **últimas 12 mensagens** da conversa (histórico) para manter
continuidade — o agente "lembra" do que foi dito anteriormente na sessão.

O histórico é lido do banco N8N (tabela `mensagens`), onde o backend Node.js
salva cada mensagem do usuário e do assistente.

> **v1.1:** Limite aumentado de 6 para 12 mensagens para melhor continuidade em conversas longas.

---

## Âncora Temporal (v1.1 — novo)

A **data atual é injetada automaticamente** no topo do system prompt em toda chamada ao ChatGPT:

```
**Data de hoje:** 13/04/2026 (domingo)
Use essa data como referência absoluta para "hoje", "este mês", "este ano", etc.
NUNCA invente ou assuma datas sem usar este valor.
```

Isso elimina a alucinação temporal — o LLM sabia responder perguntas mas não sabia
que data era hoje, levando a respostas com anos errados ou datas inventadas.

---

## Personalidade por Agente

Cada agente tem seu próprio `system_prompt` definido em `agents.py`, que instrui
o ChatGPT sobre como se comportar, o que sabe e como deve responder.

A Ayla, por exemplo, é instruída a:
- Responder em português do Brasil de forma natural e calorosa
- Não inventar dados de produção (eles vêm do banco)
- Orientar o usuário a reformular perguntas de dados quando necessário
- Ser breve e objetiva (máximo 3 parágrafos)
- Usar a data injetada como referência para períodos relativos (v1.1)

---

## Modo Offline (Fallback)

Se a `OPENAI_API_KEY` não estiver configurada no `.env`, o sistema funciona em
**modo offline** e retorna respostas fixas de fallback para smalltalk e clarify.

O log do serviço indicará:
```
[Ayla] OPENAI_API_KEY não definida — modo offline (fallback fixo).
```

Quando a chave está configurada corretamente:
```
[Ayla] ChatGPT ativo | modelo: gpt-4o-mini
```

---

## Configuração da Chave OpenAI

Arquivo: `ai_service_base/ai_service/.env`

```env
OPENAI_API_KEY=sk-proj-SuaChaveAqui
OPENAI_MODEL=gpt-4o-mini
```

Obtenha a chave em: https://platform.openai.com/api-keys

---

## Arquivo de Implementação

`ai_service_base/ai_service/app/llm_handler.py`

Classe `LLMHandler`:
- `__init__(agent_name, system_prompt)` — inicializa com o contexto do agente
- `respond(message, history, intent)` — chama a API e retorna a resposta
- `enabled` — property que indica se a API está ativa
