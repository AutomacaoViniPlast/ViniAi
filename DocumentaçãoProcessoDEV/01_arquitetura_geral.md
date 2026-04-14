# ViniAI — Arquitetura Geral do Sistema

**Versão:** 3.0  
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
         │ PostgreSQL (N8N)              │ SQL Server (METABASE)
         ▼                               ▼
┌────────────────┐             ┌──────────────────────┐
│   Banco N8N    │             │  SQL Server METABASE  │
│ 192.168.1.85   │             │   192.168.1.83        │
│   porta 5432   │             │   porta 50172         │
│                │             │                       │
│ Histórico de   │             │ Dados industriais     │
│ conversas e    │             │ STG_KARDEX            │
│ mensagens      │             │ STG_PROD_SH6_VPLONAS  │
└────────────────┘             │ STG_PROD_SD3          │
                               └──────────────────────┘
```

---

## Serviços e Portas

| Serviço | Tecnologia | Porta | Responsabilidade |
|---------|-----------|-------|-----------------|
| Frontend | React + Vite | 3003 | Interface do usuário |
| Backend | Node.js + Express | 4000 | Autenticação, JWT, histórico |
| AI Service | Python + FastAPI | 8000 | Agentes, SQL, ChatGPT |
| **SQL Server METABASE** | **SQL Server** | **50172** | **Dados industriais de produção** |
| PostgreSQL N8N | PostgreSQL | 5432 | Histórico de conversas |

---

## Separação de Bancos de Dados

| Banco | Tecnologia | IP:Porta | Uso |
|-------|-----------|----------|-----|
| METABASE | SQL Server | 192.168.1.83:50172 | Dados industriais (produção, kardex, PCP) |
| N8N | PostgreSQL | 192.168.1.85:5432 | Histórico de conversas, usuários, sessões |

**Regra:** Toda consulta a dados de produção vai ao SQL Server. O PostgreSQL permanece exclusivamente para o histórico de conversa da IA (tabela `mensagens` no banco N8N).

---

## Fluxo de uma Mensagem

```
1. Usuário digita mensagem no frontend
2. Backend Node.js (porta 4000) salva a mensagem do usuário no banco N8N (PostgreSQL)
3. Frontend envia POST /v1/chat/process diretamente ao FastAPI (porta 8000)
   → payload inclui: message, session_id, user_id, user_name, user_setor, user_cargo
4. FastAPI (Orchestrator):
   a. Lê últimas 16 mensagens da conversa no banco N8N — PostgreSQL (context_manager)
   b. Interpreta a intenção (RuleBasedInterpreter — 19 regras, sem custo de LLM)
   c. Verifica permissão LGPD (permissions.py)
      → Se negado: retorna mensagem formal de LGPD
   d. RAG Conversacional:
      → Mensagem ambígua + período novo → herda intent SQL do histórico
      → SQL sem período explícito (conf < 0.87) → herda período da última msg c/ data
   e. Auto-inject: intent de operador + entity_value=None → injeta login do usuário logado
   f. Roteia:
      → Conversa natural (smalltalk/clarify) → ChatGPT com data atual injetada no prompt
      → Consulta de dados (sql) → SQLService → SQL Server METABASE (STG_KARDEX)
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
│   ├── db.py               → conexões: get_mssql_conn() SQL Server + get_n8n_conn() PostgreSQL N8N
│   ├── interpreter.py      → classificação de intenção por 19 regras regex + parsing de períodos
│   ├── llm_handler.py      → integração com ChatGPT (OpenAI API) — injeta data atual no prompt
│   ├── orchestrator.py     → orquestrador principal: RAG, period-inherit, auto-inject, roteamento
│   ├── permissions.py      → controle de acesso por departamento + mensagem LGPD formal
│   ├── schemas.py          → modelos Pydantic (ChatProcessRequest, ChatProcessResponse, etc.)
│   └── sql_service.py      → queries SQL contra dbo.STG_KARDEX no SQL Server (produção, LD, rankings)
├── .env                    → variáveis de ambiente (NÃO versionar)
├── requirements.txt        → dependências Python
└── test_llm.py             → testes do LLMHandler e do interpretador
```

### Regra de importações (anti-circular)

```
config          → sem dependências internas
db              → sem dependências internas
sql_service     → importa db (get_mssql_conn)
interpreter     → importa config, schemas
permissions     → sem dependências internas
agents          → sem dependências internas
context_manager → importa db (get_n8n_conn), schemas
llm_handler     → importa schemas
orchestrator    → importa tudo acima + context_manager + llm_handler
main            → importa orchestrator, schemas
```

---

## Tabelas SQL Server (METABASE)

### dbo.STG_KARDEX — tabela principal de movimentações

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| USUARIO | varchar(25) | Login do operador (com espaços — usar LTRIM/RTRIM) |
| EMISSAO | date | Data da movimentação (tipo nativo — sem conversão) |
| PRODUTO | varchar(15) | Código do produto |
| QUALIDADE | varchar(1) | **'Y'=LD (defeito), 'I'=Inteiro** |
| TOTAL | float | Peso em KG |
| TURNO | varchar(5) | Turno de produção (ex: 06-14, 14-22, 22-06) |
| ORIGEM | varchar(3) | SD1=Entrada, SD2=Saída, SD3=Movimentação Interna |

### dbo.STG_PROD_SH6_VPLONAS — apontamentos de produção

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| OPERADOR | varchar(10) | Código numérico do operador |
| NOME_OPERADOR | varchar(55) | Nome do operador |
| DATA_APONT | date | Data do apontamento |
| DATA_TURNO | date | Data por turno |
| QTDPROD | float | Quantidade produzida |
| PESO_TECIDO | float | Peso do tecido em KG |
| HORAS | float | Horas trabalhadas |
| KGH | float | KG por hora |
| TIPO_PROD | varchar(1) | Y=LD, I=Inteiro |
| PRODUTO | varchar(15) | Código do produto |
| MOTIVO_Y | varchar(40) | Motivo do defeito LD |

### dbo.STG_PROD_SD3 — movimentações SD3

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| USUARIO | varchar(25) | Login do operador |
| EMISSAO | date | Data |
| PRODUTO | varchar(15) | Código do produto |
| TM | varchar(3) | Tipo de movimento (010, 100, 499, 502, 999) |
| TIPO_PROD | varchar(2) | Tipo de produto |
| QTDE1UM / QTDE2UM | float | Quantidades |
| LOCAL_OP | varchar(2) | Local de operação |
| MOT_PERDA / DESC_MOTIVO | varchar | Motivo de perda |

---

## Variáveis de Ambiente Necessárias

Arquivo: `ai_service_base/ai_service/.env`

```env
# SQL Server — dados industriais (METABASE)
MSSQL_HOST=192.168.1.83
MSSQL_PORT=50172
MSSQL_DB=METABASE
MSSQL_USER=sa
MSSQL_PASSWORD=...
MSSQL_DRIVER=ODBC Driver 17 for SQL Server

# PostgreSQL N8N — histórico de conversas
N8N_DB_HOST=192.168.1.85
N8N_DB_PORT=5432
N8N_DB_NAME=N8N
N8N_DB_USER=postgres
N8N_DB_PASSWORD=...

# ChatGPT / OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
```

**Dependências adicionais no servidor:** ODBC Driver 17 for SQL Server deve estar instalado no Windows.

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
