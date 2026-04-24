# PostgreSQL — N8N

## Conexão

| Campo | Valor |
|-------|-------|
| Host | 192.168.1.85 |
| Porta | 5432 |
| Banco | N8N |
| Usuário | postgres |
| Pool | psycopg-pool (min=1, max=5) |
| Variáveis `.env` | `N8N_DB_HOST`, `N8N_DB_PORT`, `N8N_DB_NAME`, `N8N_DB_USER`, `N8N_DB_PASSWORD` |

> [!warning] Uso exclusivo
> Este banco é usado **SOMENTE** para autenticação de usuário, conversas e mensagens.
> Nenhum dado industrial vai aqui.

---

## Responsabilidade no sistema

O PostgreSQL N8N tem dois papéis distintos no ViniAI:

### 1. Autenticação de usuários
Gerenciado pelo **Backend Node.js** (porta 4000). Armazena usuários, credenciais e sessões JWT.

### 2. Histórico de conversas
Tabela `mensagens` — armazena cada turn da conversa (usuário + assistente).

O **AI Service (FastAPI)** acessa este banco em **somente leitura** via `context_manager.py`:
- Lê as últimas **16 mensagens** da sessão antes de processar cada request
- Nunca grava diretamente — quem grava é o Backend Node.js

---

## Fluxo de gravação do histórico

```
1. Usuário envia mensagem
2. Backend Node.js salva mensagem do USUÁRIO no PostgreSQL (antes de chamar FastAPI)
3. FastAPI processa e retorna resposta
4. Backend Node.js salva resposta do ASSISTENTE no PostgreSQL
```

> [!note] Stateless por design
> O AI Service não mantém estado em memória — todo o contexto vem do banco a cada request.
> Isso permite escalar o FastAPI horizontalmente sem problemas.

---

## Acesso no código

```python
# db.py — pool de conexões
from psycopg_pool import ConnectionPool

# context_manager.py — uso
with get_n8n_conn() as conn:
    rows = conn.execute(
        "SELECT role, conteudo FROM mensagens WHERE conversa_id = %s ORDER BY criado_em DESC LIMIT %s",
        (session_id, limit)
    ).fetchall()
```

> [!note] Diferença de parâmetros
> PostgreSQL usa `%s` (psycopg). SQL Server usa `?` (pyodbc). Nunca misturar.

---

## Inicialização tolerante a falha

O pool N8N é inicializado no startup do FastAPI. Se o banco estiver indisponível, o serviço sobe mesmo assim — histórico de conversa fica desabilitado, mas o agente ainda responde.

Log de erro: `[db] Pool N8N não inicializado — histórico de conversa desabilitado: ...`

---

## Links relacionados

- [[SQLServer]] — banco de dados industriais
- [[Arquitetura-Geral]] — contexto de uso dos dois bancos
- [[RAG-Conversacional]] — como o histórico é usado no contexto da IA
