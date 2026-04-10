# ViniAI — Arquitetura Geral do Sistema

**Versão:** 1.0  
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
2. Frontend envia POST /v1/chat/process para o FastAPI (porta 8000)
   → payload inclui: message, session_id, user_id, user_setor
3. FastAPI (Orchestrator):
   a. Lê histórico da conversa (banco N8N)
   b. Interpreta a intenção (RuleBasedInterpreter — sem LLM)
   c. Verifica permissão LGPD (permissions.py)
      → Se negado: retorna mensagem formal de LGPD
   d. Roteia:
      → Conversa natural (smalltalk/clarify) → ChatGPT (OpenAI)
      → Consulta de dados → SQL direto no banco METABASE
4. Resposta formatada retorna ao frontend
5. Frontend exibe a resposta e salva mensagem no backend Node.js
6. Backend Node.js salva no banco N8N (histórico)
```

---

## Estrutura de Arquivos — AI Service

```
ai_service_base/ai_service/
├── app/
│   ├── __init__.py         → índice do pacote com mapa de módulos
│   ├── main.py             → endpoints FastAPI e configuração de CORS
│   ├── agents.py           → registro de todos os agentes (nome, domínio, prompts)
│   ├── config.py           → setores, operadores e origens (FONTE DA VERDADE)
│   ├── context_manager.py  → leitura do histórico de conversa (banco N8N)
│   ├── db.py               → pools de conexão PostgreSQL (METABASE e N8N)
│   ├── interpreter.py      → classificação de intenção por regras (sem LLM)
│   ├── llm_handler.py      → integração com ChatGPT (OpenAI API)
│   ├── orchestrator.py     → orquestrador principal (coordena todo o fluxo)
│   ├── permissions.py      → controle de acesso por perfil + mensagem LGPD
│   └── schemas.py          → modelos Pydantic (estrutura de entrada e saída)
├── .env                    → variáveis de ambiente (NÃO versionar)
├── requirements.txt        → dependências Python
└── test_llm.py             → testes do LLMHandler e do interpretador
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

# Verificar status
nssm status ViniAI-FastAPI

# Ver todos os serviços
nssm status ViniAI-FastAPI
nssm status ViniAI-Backend
nssm status ViniAI-Frontend
```
