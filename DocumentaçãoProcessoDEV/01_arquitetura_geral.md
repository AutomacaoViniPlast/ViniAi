# ViniAI — Arquitetura Geral do Sistema

**Versão:** 3.4  
**Última atualização:** Maio/2026  
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
│ conversas e    │             │ STG_KARDEX (principal)│
│ mensagens      │             │ STG_PROD_SH6          │
└────────────────┘             │ STG_PROD_SD3          │
                               │ STG_APONT_REV_GERAL   │
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

| Banco | Tecnologia | IP:Porta | Responsabilidade exclusiva |
|-------|-----------|----------|---------------------------|
| METABASE | SQL Server | 192.168.1.83:50172 | **Dados industriais** — produção, kardex, revisão, expedição |
| N8N | PostgreSQL | 192.168.1.85:5432 | **Autenticação de usuário, conversas e mensagens** |

**Regra fixa de separação:**
- **SQL Server** → SOMENTE consultas de dados industriais (STG_KARDEX e demais tabelas do METABASE)
- **PostgreSQL** → SOMENTE autenticação de usuário, histórico de conversas e tabela de mensagens
- Nenhum dado industrial vai ao PostgreSQL. Nenhum dado de autenticação/conversa vai ao SQL Server.

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
│   ├── interpreter.py           → classificação de intenção por 22+ regras regex + parsing de períodos
│   ├── llm_handler.py           → integração com ChatGPT (OpenAI API) — injeta data atual no prompt
│   ├── orchestrator.py          → orquestrador principal: RAG, period-inherit, auto-inject, roteamento
│   ├── permissions.py           → controle de acesso por departamento + mensagem LGPD formal
│   ├── schemas.py               → modelos Pydantic (ChatProcessRequest, ChatProcessResponse, etc.)
│   ├── sql_service_sh6.py       → queries SQL — dbo.STG_PROD_SH6_VPLONAS (produção, KGH, horas)
│   ├── sql_service_kardex.py    → queries SQL — dbo.V_KARDEX (qualidade, LD, produto, família)
│   └── sql_service_apont_rev.py → queries SQL — dbo.V_APONT_REV_GERAL (revisão em metros + ranking de produção extrusora)
├── .env                         → variáveis de ambiente (NÃO versionar)
├── requirements.txt             → dependências Python
└── test_interpreter_*.py        → testes do interpretador por domínio (kardex, sh6, periodos, etc.)
```

### Regra de importações (anti-circular)

```
config                → sem dependências internas
db                    → sem dependências internas
sql_service_sh6       → importa db (get_mssql_conn)
sql_service_kardex    → importa db (get_mssql_conn)
sql_service_apont_rev → importa db (get_mssql_conn)
interpreter           → importa config, schemas
permissions           → sem dependências internas
agents                → sem dependências internas
context_manager       → importa db (get_n8n_conn), schemas
llm_handler           → importa schemas
orchestrator          → importa tudo acima + context_manager + llm_handler
main                  → importa orchestrator, schemas
```

---

## Tabelas SQL Server (METABASE)

> **Tabela principal para todas as consultas atuais:** `dbo.STG_KARDEX`  
> As demais tabelas serão integradas conforme novos agentes e funcionalidades forem desenvolvidos.

### dbo.STG_KARDEX — tabela principal (mais completa)

Abrange todo o ciclo industrial de produção:
- **Matéria-prima:** entrada de CARBONATO, RESINA, DRAPEX, DOP
- **Produção:** 1ª, 2ª e 3ª passada do filme plástico na extrusora
- **Revisão:** inspeção das bobinas — identificação de defeitos por metro

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| USUARIO | varchar(25) | Login do operador (com espaços — usar LTRIM/RTRIM) |
| EMISSAO | date | Data da movimentação (tipo nativo — sem conversão) |
| PRODUTO | varchar(15) | Código do produto (posição 5 = Y ou I) |
| QUALIDADE | varchar(1) | **'Y'=LD (defeito), 'I'=Inteiro** — pré-calculado da posição 5 do produto |
| TOTAL | float | Quantidade em KG |
| TURNO | varchar(5) | Turno de produção (ex: 06-14, 14-22, 22-06) |
| ORIGEM | varchar(3) | SD1=Entrada, SD2=Saída, SD3=Movimentação Interna |

> **Regra LD:** usar `QUALIDADE = 'Y'` nas queries (não usar SUBSTRING do produto — já está pré-calculado).  
> **Filtro por ORIGEM é opcional** — muitos registros têm ORIGEM NULL.

### dbo.STG_PROD_SH6 (STG_PROD_SH6_VPLONAS) — apontamentos de produção

Focada em produção, aborda movimentações internas com nível de detalhe operacional maior que o KARDEX. Inclui horas trabalhadas, KG/hora e motivo do defeito LD.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| OPERADOR | varchar(10) | Código numérico do operador |
| NOME_OPERADOR | varchar(55) | Nome do operador |
| DATA_APONT | date | Data do apontamento |
| DATA_TURNO | date | Data por turno |
| QTDPROD | float | Quantidade produzida |
| PESO_TECIDO | float | Peso do tecido em KG |
| HORAS | float | Horas trabalhadas |
| KGH | float | KG por hora (eficiência) |
| TIPO_PROD | varchar(1) | Y=LD, I=Inteiro |
| PRODUTO | varchar(15) | Código do produto |
| MOTIVO_Y | varchar(40) | Motivo do defeito LD |

### dbo.STG_PROD_SD3 — movimentações internas

Tabela de movimentação interna da empresa (produção de bobinas). Contém tipos de movimento e motivos de perda de material.

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

### dbo.V_APONT_REV_GERAL — apontamentos de revisão e produção extrusora (view)

View usada por dois contextos distintos: revisão de bobinas e ranking de produção da extrusora.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| OPER_BOB | varchar | Login do operador de **revisão** (ex: kaua.chagas) |
| OPER_MP | varchar | Login do operador de **extrusora/produção** (ex: aramis.leal) |
| PRODUTO | varchar | Código do produto; posição 5: I=Inteiro, P=Fora de Padrão, Y=LD |
| QTDPROD | float | Metros — principal para produção extrusora e revisão INTEIRO/FP |
| QTDPROD2 | float | Metros — usado para revisão LD e demais tipos |
| DATAAPONT | datetimeoffset | Data/hora do apontamento (fuso -03:00) |
| MOTPERDA | varchar | Motivo de perda (incluído no total de revisão) |

**Fórmula de metros — Revisão** (replicada do Metabase, usa CASE por tipo de produto):
```
METROS = QTDPROD   se SUBSTRING(PRODUTO, 5, 1) IN ('I', 'P')
       = QTDPROD2  caso contrário
```

**Fórmula de metros — Produção Extrusora** (todos os registros usam QTDPROD):
```
METROS = COALESCE(QTDPROD, 0)
```

**Filtro de data:** `CAST(DATAAPONT AS DATE) BETWEEN CONVERT(date, ?, 103) AND CONVERT(date, ?, 103)`  
**Revisão:** filtrar por `LOWER(LTRIM(RTRIM(OPER_BOB)))` — logins definidos em `config.py` (OPERADORES_REVISAO).  
**Produção extrusora:** filtrar por `LOWER(LTRIM(RTRIM(OPER_MP)))` — sem whitelist, retorna todos com registro.

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

## Infraestrutura de Servidores

| Servidor | IP | Serviços |
|----------|----|---------|
| ~~Servidor antigo (comprometido)~~ | ~~192.168.1.84~~ | ~~Frontend, FastAPI~~ |
| **Servidor atual** | **192.168.1.85** | **Todos os serviços + PostgreSQL + n8n** |
| SQL Server METABASE | 192.168.1.83 | Dados industriais |

> **Nota:** O servidor 192.168.1.84 foi comprometido (vírus, firewall desativado) em Abril/2026. Todos os serviços foram migrados para 192.168.1.85.

---

## Gerenciamento de Serviços (Windows Server + NSSM)

Cada serviço usa um **wrapper bat** como inicializador, necessário para garantir o diretório de trabalho correto ao rodar como serviço Windows.

| Serviço NSSM | Bat wrapper | Porta |
|---|---|---|
| `ViniAI-CerebroIA` | `ai_service_base\ai_service\start_cerebro.bat` | 8000 |
| `ViniAI-Backend` | `backend\start_backend.bat` | 4000 |
| `ViniAI-Frontend` | `frontAI\start_frontend.bat` | 3003 |

**Configuração NSSM de cada serviço:**

| Campo | Valor |
|---|---|
| Path | `C:\Windows\System32\cmd.exe` |
| Startup directory | pasta do serviço |
| Arguments | `/c start_<nome>.bat` |

```cmd
# Comandos úteis
C:\NSSM\nssm.exe restart ViniAI-CerebroIA
C:\NSSM\nssm.exe restart ViniAI-Backend
C:\NSSM\nssm.exe restart ViniAI-Frontend

C:\NSSM\nssm.exe status ViniAI-CerebroIA
C:\NSSM\nssm.exe status ViniAI-Backend
C:\NSSM\nssm.exe status ViniAI-Frontend
```

> **Localização do NSSM:** `C:\NSSM\nssm.exe`  
> **Logs dos serviços:** `C:\Users\pedro.martins\Documents\ViniAi\logs\`  
> **Conta de serviço:** LocalSystem

### Firewall — portas liberadas na .85

```cmd
netsh advfirewall firewall add rule name="ViniAI Frontend 3003" dir=in action=allow protocol=TCP localport=3003
netsh advfirewall firewall add rule name="ViniAI Backend 4000" dir=in action=allow protocol=TCP localport=4000
netsh advfirewall firewall add rule name="ViniAI FastAPI 8000" dir=in action=allow protocol=TCP localport=8000
```

---

## Integração WhatsApp (Meta)

O ViniAI suporta acesso via WhatsApp além do frontend web.

| Item | Referência |
|------|-----------|
| **Gerenciar perfil do número** | Meta Business Suite |
| **API e configurações técnicas** | Facebook Developers (developers.facebook.com) |
| **Provedor da API** | Meta (WhatsApp Business Platform) |

- **Perfil do número** (nome, foto, descrição): gerenciado pelo **Meta Business Suite**
- **Webhook, token, configurações de API**: gerenciados no portal **Facebook Developers**
