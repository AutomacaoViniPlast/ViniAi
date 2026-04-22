# Arquitetura Geral

## Diagrama de Serviços

```
┌─────────────────────────────────────────────────────────┐
│                     USUÁRIO (Browser)                    │
│              viniai.viniplast.local:3003                 │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP
          ┌──────────────┴──────────────┐
          │                             │
          ▼                             ▼
┌─────────────────┐          ┌──────────────────────┐
│  Backend Node.js │          │   FastAPI (Python)    │
│   porta 4000     │◄────────►│      porta 8000       │
│  - Auth / JWT    │          │  - Agentes de IA      │
│  - Histórico     │          │  - Interpretador      │
│  - Conversas     │          │  - SQL / ChatGPT      │
└────────┬─────────┘          └──────────┬────────────┘
         │                               │
    PostgreSQL N8N                  SQL Server
    192.168.1.85:5432            192.168.1.83:50172
    Banco: N8N                   Banco: METABASE
    Auth + Histórico             Dados Industriais
```

---

## IPs e Portas

| Componente | IP | Porta |
|-----------|-----|-------|
| Frontend + Backend | 192.168.1.84 | 3003 / 4000 |
| AI Service (FastAPI) | 192.168.1.111 | 8000 |
| SQL Server METABASE | 192.168.1.83 | 50172 |
| PostgreSQL N8N | 192.168.1.85 | 5432 |
| N8N (automações) | 192.168.1.85 | 5678 |

---

## Fluxo de uma Mensagem

```
1. Usuário digita no frontend (porta 3003)
2. Backend Node.js (4000) salva mensagem do usuário no PostgreSQL N8N
3. Frontend POST /v1/chat/process → FastAPI (8000)
   payload: { message, session_id, user_id, user_name, user_setor, user_cargo }
4. FastAPI (Orchestrator):
   a. Lê últimas 16 msgs da conversa (context_manager → PostgreSQL N8N)
   b. Interpreta intenção (RuleBasedInterpreter — 19 regras, sem custo de LLM)
   c. Verifica permissão LGPD (permissions.py)
   d. RAG Conversacional:
      → clarify + período novo → herda intent SQL do histórico
      → SQL sem período + conf < 0.87 → herda período da última msg com data
   e. Auto-inject: intent de operador + entity=None → injeta login do usuário
   f. Roteia:
      → smalltalk/clarify → ChatGPT (data atual injetada no system prompt)
      → sql → SQLService → SQL Server METABASE (STG_KARDEX)
5. Resposta retorna ao frontend
6. Backend Node.js salva resposta no PostgreSQL N8N (histórico)
```

---

## Estrutura de Arquivos — AI Service

```
ai_service_base/ai_service/
├── app/
│   ├── main.py             → FastAPI: GET /health, POST /v1/chat/process, CORS
│   ├── agents.py           → registro de agentes (nome, system_prompt, capabilities)
│   ├── config.py           → FONTE DA VERDADE: setores, operadores, origens
│   ├── context_manager.py  → leitura do histórico no PostgreSQL N8N (somente leitura)
│   ├── db.py               → get_mssql_conn() + get_n8n_conn()
│   ├── interpreter.py      → 19 regras regex + parsing de períodos
│   ├── llm_handler.py      → ChatGPT com date.today() injetado em toda chamada
│   ├── orchestrator.py     → RAG, period-inherit, auto-inject, roteamento
│   ├── permissions.py      → controle de acesso por departamento + LGPD
│   ├── schemas.py          → modelos Pydantic
│   └── sql_service.py      → queries SQL contra dbo.STG_KARDEX
├── .env                    → variáveis de ambiente (não versionado)
└── requirements.txt
```

### Regra anti-circular de imports

```
config / db / permissions / agents  → sem deps internas
sql_service     → importa db
interpreter     → importa config, schemas
context_manager → importa db, schemas
llm_handler     → importa schemas
orchestrator    → importa tudo acima
main            → importa orchestrator, schemas
```

---

## Fontes de verdade

| Fonte | Papel |
|-------|-------|
| SQL Server METABASE | Dados industriais operacionais (somente leitura pelo AI Service) |
| PostgreSQL N8N | Autenticação + histórico de conversas + mensagens |
| `app/config.py` | Setores, operadores e origens (fonte da verdade do código) |
| Obsidian (este vault) | Memória longa do projeto — arquitetura, decisões, convenções |
| CLAUDE.md | Resumo persistente para o Claude Code |

---

## Links relacionados

- [[SQLServer]] — tabelas e regras de query
- [[PostgreSQL]] — banco N8N e histórico
- [[Agentes]] — registro de agentes
- [[Interpretacao-de-Intencao]] — como o interpretador funciona
- [[RAG-Conversacional]] — carry-over, period-inherit
- [[Deploy]] — NSSM e variáveis de ambiente