# RunBook — Deploy e Operações

## Gerenciamento de Serviços (NSSM)

O servidor Windows gerencia os três serviços do ViniAI via NSSM.

**Executável:** `C:\metabase\nssm.exe`

### Comandos essenciais

```cmd
# Reiniciar o AI Service após atualização de código
nssm restart ViniAI-FastAPI

# Verificar status de cada serviço
nssm status ViniAI-FastAPI
nssm status ViniAI-Backend
nssm status ViniAI-Frontend
```

**Status esperado após deploy:** `SERVICE_RUNNING`

### Localização dos serviços no servidor

| Serviço | Caminho |
|---------|---------|
| AI Service (FastAPI) | `C:\Users\pedro.martins\Documents\ViniAi\ai_service_base\ai_service\` |
| Backend Node.js | `C:\Users\pedro.martins\Documents\ViniAi\backend\dist\server.js` |
| Frontend React | `C:\Users\pedro.martins\Documents\ViniAi\frontAI\dist\` |
| Logs | `C:\Users\pedro.martins\Documents\ViniAi\logs\` |

> [!warning]
> O usuário Windows no servidor é `pedro.martins`, não `Martins`.
> O NSSM está configurado com conta `pedro.martins` na aba "Log On".

---

## Fluxo de Deploy

```
1. Desenvolver e testar localmente
2. git add / git commit / git push (main)
3. No servidor: git pull
4. nssm restart ViniAI-FastAPI
5. nssm status ViniAI-FastAPI → deve retornar SERVICE_RUNNING
6. Testar uma mensagem na interface
```

---

## Variáveis de Ambiente — AI Service

Arquivo: `ai_service_base/ai_service/.env`

> [!warning] Não versionar
> O `.env` está no `.gitignore`. Nunca commitar este arquivo.

**Variáveis obrigatórias:**

```
# SQL Server — dados industriais
MSSQL_HOST=192.168.1.83
MSSQL_PORT=50172
MSSQL_DB=METABASE
MSSQL_USER=sa
MSSQL_PASSWORD=<senha>
MSSQL_DRIVER=ODBC Driver 17 for SQL Server

# PostgreSQL N8N — histórico de conversas
N8N_DB_HOST=192.168.1.85
N8N_DB_PORT=5432
N8N_DB_NAME=N8N
N8N_DB_USER=postgres
N8N_DB_PASSWORD=<senha>

# OpenAI
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL=gpt-4o-mini
```

> [!note] Variáveis antigas (não usar)
> As variáveis `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` são da era PostgreSQL.
> O código atual usa `MSSQL_*`. Se o `.env` estiver com `DB_*`, o FastAPI não sobe.

---

## Dependências do Servidor

| Dependência | Onde instalar | Para que |
|------------|--------------|---------|
| Python 3.14 | `C:\Python314\` | Runtime do AI Service |
| ODBC Driver 17 for SQL Server | Windows (sistema) | pyodbc → SQL Server |
| pyodbc | `.venv` do AI Service | Conexão ao SQL Server |
| psycopg-pool | `.venv` do AI Service | Conexão ao PostgreSQL |

### Instalando no ambiente virtual correto

```cmd
C:\Users\pedro.martins\Documents\ViniAi\ai_service_base\ai_service\.venv\Scripts\pip install pyodbc
```

> [!warning]
> `pip install pyodbc` no sistema (fora do `.venv`) não tem efeito — o NSSM usa o `.venv`.
> Sempre instalar dentro do `.venv` do AI Service.

---

## Diagnóstico de Erros Comuns

| Erro no log | Causa | Solução |
|-------------|-------|---------|
| `ModuleNotFoundError: No module named 'pyodbc'` | pyodbc instalado fora do .venv | Instalar dentro do `.venv` |
| `KeyError: 'MSSQL_DRIVER'` | `.env` com variáveis antigas (`DB_*`) | Atualizar `.env` com `MSSQL_*` |
| Pool N8N não inicializado | PostgreSQL N8N indisponível no startup | Verificar conectividade 192.168.1.85:5432 |
| `SERVICE_STOP_PENDING` no NSSM | Serviço travado | `nssm stop ViniAI-FastAPI` + `nssm start ViniAI-FastAPI` |

---

## Links relacionados

- [[Arquitetura-Geral]] — mapa de IPs e serviços
- [[PostgreSQL]] — configuração do banco de histórico
- [[SQLServer]] — configuração do banco industrial
