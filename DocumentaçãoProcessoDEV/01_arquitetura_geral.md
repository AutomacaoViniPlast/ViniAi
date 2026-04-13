# ViniAI — Arquitetura Geral do Sistema

**Versão:** 2.0  
**Última atualização:** Abril/2026  
**Responsável técnico:** TI / Desenvolvimento

---

## Visão Geral

O ViniAI é uma plataforma de inteligência artificial industrial da Viniplast, composta por múltiplos agentes especializados por departamento. Cada agente tem nome próprio, personalidade e domínio de dados específico.

O sistema é dividido em três serviços independentes que se comunicam entre si:

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
│   porta 4000     │          │      porta 8000       │
│                  │          │                       │
│  - Autenticação  │          │  - Agentes de IA      │
│  - JWT           │◄────────►│  - Interpretação      │
│  - Histórico     │          │  - SQL / ChatGPT      │
│  - Conversas     │          │  - Controle de acesso │
└────────┬─────────┘          └──────────┬────────────┘
         │                               │
         └──────────────┬────────────────┘
                        │ PostgreSQL
              ┌─────────┴──────────┐
              │                    │
              ▼                    ▼
     ┌────────────────┐   ┌────────────────┐
     │  Banco METABASE │   │   Banco N8N    │
     │ 192.168.1.85   │   │ 192.168.1.85   │
     │   porta 5432   │   │   porta 5432   │
     │                │   │                │
     │ Dados de       │   │ Histórico de   │
     │ produção       │   │ conversas e    │
     │ (v_kardex_ld)  │   │ mensagens      │
     └────────────────┘   └────────────────┘
```

---

## Serviços e Portas

| Serviço | Tecnologia | Porta | Responsabilidade |
|---------|-----------|-------|-----------------|
| Frontend | React + Vite | 3003 | Interface do usuário |
| Backend | Node.js + Express | 4000 | Autenticação, JWT, histórico |
| AI Service | Python + FastAPI | 8000 | Agentes, SQL, ChatGPT |
| PostgreSQL METABASE | PostgreSQL | 5432 | Dados de produção |
| PostgreSQL N8N | PostgreSQL | 5432 | Histórico de conversas |

---

## Fluxo de uma Mensagem

```
1. Usuário digita mensagem no frontend
2. Backend Node.js (porta 4000) salva a mensagem do usuário no banco N8N
3. Frontend envia POST /v1/chat/process diretamente ao FastAPI (porta 8000)
   → payload inclui: message, session_id, user_id, user_name, user_setor, user_cargo
4. FastAPI (Orchestrator):
   a. Lê últimas 16 mensagens da conversa no banco N8N (context_manager)
   b. Interpreta a intenção (RuleBasedInterpreter — 19 regras, sem custo de LLM)
   c. Verifica permissão LGPD (permissions.py)
      → Se negado: retorna mensagem formal de LGPD
   d. RAG Conversacional:
      → Mensagem ambígua + período novo → herda intent SQL do histórico
      → SQL sem período explícito (conf < 0.87) → herda período da última msg c/ data
   e. Auto-inject: intent de operador + entity_value=None → injeta login do usuário logado
   f. Roteia:
      → Conversa natural (smalltalk/clarify) → ChatGPT com data atual injetada no prompt
      → Consulta de dados (sql) → SQLService direto no banco METABASE
5. Resposta formatada retorna ao frontend
6. Backend Node.js salva a resposta do assistente no banco N8N (histórico)
```

---

## Estrutura de Arquivos — AI Service

```
ai_service_base/ai_service/
├── app/
│   ├── __init__.py         → índice do pacote com mapa de módulos
│   ├── main.py             → endpoints FastAPI (GET /health, POST /v1/chat/process) e CORS
│   ├── agents.py           → registro de todos os agentes (nome, domínio, system_prompt, capabilities)
│   ├── config.py           → setores, operadores e origens (FONTE DA VERDADE)
│   ├── context_manager.py  → leitura do histórico de conversa no banco N8N (somente leitura)
│   ├── db.py               → pools de conexão psycopg_pool (METABASE pool=10, N8N pool=5)
│   ├── interpreter.py      → classificação de intenção por 19 regras regex + parsing de períodos
│   ├── llm_handler.py      → integração com ChatGPT (OpenAI API) — injeta data atual no prompt
│   ├── orchestrator.py     → orquestrador principal: RAG, period-inherit, auto-inject, roteamento
│   ├── permissions.py      → controle de acesso por departamento + mensagem LGPD formal
│   ├── schemas.py          → modelos Pydantic (ChatProcessRequest, ChatProcessResponse, etc.)
│   └── sql_service.py      → queries SQL contra v_kardex_ld (produção, LD, rankings, turnos)
├── .env                    → variáveis de ambiente (NÃO versionar)
├── requirements.txt        → dependências Python
└── test_llm.py             → testes do LLMHandler e do interpretador
```

### Regra de importações (anti-circular)

```
config      → sem dependências internas
db          → sem dependências internas
sql_service → importa db
interpreter → importa config, schemas
permissions → sem dependências internas
agents      → sem dependências internas
context_manager → importa db, schemas
llm_handler → importa schemas
orchestrator → importa tudo acima + context_manager + llm_handler
main        → importa orchestrator, schemas
```

---

## Variáveis de Ambiente Necessárias

Arquivo: `ai_service_base/ai_service/.env`

```env
# Banco de Produção (METABASE)
DB_HOST=192.168.1.85
DB_PORT=5432
DB_NAME=METABASE
DB_USER=postgres
DB_PASSWORD=...

# Banco de Conversas (N8N)
N8N_DB_HOST=192.168.1.85
N8N_DB_PORT=5432
N8N_DB_NAME=N8N
N8N_DB_USER=postgres
N8N_DB_PASSWORD=...

# ChatGPT / OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
```

---

## Gerenciamento de Serviços (Windows Server + NSSM)

```cmd
# Reiniciar o AI Service após atualização de código
nssm restart ViniAI-FastAPI

# Verificar status de cada serviço
nssm status ViniAI-FastAPI
nssm status ViniAI-Backend
nssm status ViniAI-Frontend
```

> **Localização do NSSM:** `C:\metabase\nssm.exe`  
> **Logs do serviço:** `C:\Users\pedro.martins\Documents\ViniAi\logs\`  
> **Conta de serviço:** configurada como `pedro.martins` na aba Log On do NSSM
