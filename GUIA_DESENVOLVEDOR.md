# Guia do Desenvolvedor — ViniAI

> Como entender, manter e expandir o projeto sem depender de ninguém.

---

## 1. O que é o ViniAI?

Um sistema de IA que responde perguntas em linguagem natural sobre dados industriais.
O usuário digita "Quem mais revisou esse mês?" e o sistema:

1. Entende o que foi pedido
2. Monta uma query SQL
3. Executa no banco
4. Formata e devolve a resposta em texto

Tudo isso acontece em Python (FastAPI), no serviço `ai_service_base/ai_service/`.

---

## 2. Os serviços do projeto

| Serviço | Tecnologia | Porta | O que faz |
|---------|-----------|-------|-----------|
| **CerebroIA** | Python + FastAPI | 8000 | Interpreta, consulta SQL, responde |
| **Backend** | Node.js + Express | 4000 | Autenticação JWT, salva histórico |
| **Frontend** | React + Vite | 3003 | Interface do usuário |
| **SQL Server** | METABASE | 50172 | Dados industriais (produção, revisão...) |
| **PostgreSQL** | N8N | 5432 | Histórico de conversas + session intents |

Você vai trabalhar quase sempre no **CerebroIA** (Python).

---

## 3. Os arquivos que importam

```
ai_service_base/ai_service/app/
│
├── config.py              ← Setores, operadores, origens — FONTE DA VERDADE
├── db.py                  ← Conexões: get_mssql_conn() e get_n8n_conn()
├── schemas.py             ← Modelos de dados (InterpretationResult, etc.)
├── agents.py              ← Personalidade da Ayla (system prompt)
├── permissions.py         ← Quem pode ver o quê (LGPD)
│
├── interpreter.py         ← PASSO 1: lê a mensagem, identifica a intenção
├── orchestrator.py        ← PASSO 2: roteia, chama SQL, formata resposta
│
├── sql_service_sh6.py     ← SQL: produção das extrusoras (STG_PROD_SH6_VPLONAS)
├── sql_service_kardex.py  ← SQL: qualidade/LD/expedição (V_KARDEX)
├── sql_service_apont_rev.py ← SQL: apontamentos de revisão (STG_APONT_REV_GERAL)
│
├── context_manager.py     ← Lê histórico do PostgreSQL, salva session intents
├── llm_handler.py         ← Chama o ChatGPT para respostas conversacionais
└── main.py                ← Endpoints FastAPI (/health, /v1/chat/process)
```

**Regra de ouro de importação** — nunca importe de cima para baixo na lista acima.
`interpreter` pode importar `config`, mas `config` nunca importa `interpreter`.
Isso evita circular import.

---

## 4. O fluxo completo de uma mensagem

```
Usuário digita: "Quem mais revisou esse mês?"
        │
        ▼
[ interpreter.py ]
  • Testa ~19 regras regex em ordem
  • Extrai: intent="ranking_revisao", período="01/04 a 30/04", top_n=5
  • Retorna InterpretationResult
        │
        ▼
[ orchestrator.py — process() ]
  • Verifica permissão (LGPD)
  • Aplica RAG: herda período/intent do histórico se necessário
  • Chama _dispatch(ir)
        │
        ▼
[ orchestrator.py — _dispatch() ]
  • Vê que intent == "ranking_revisao"
  • Chama self.apont_rev.get_ranking_revisao(ini, fim, top_n)
        │
        ▼
[ sql_service_apont_rev.py ]
  • Executa o SQL no SQL Server
  • Retorna lista de dicts: [{operador, total_kg, registros}, ...]
        │
        ▼
[ orchestrator.py — _dispatch() ]
  • Formata o resultado em texto Markdown
  • Retorna a string final
        │
        ▼
Usuário recebe: "🏆 Top 5 — Revisão (KG revisados) em Abril de 2026..."
```

---

## 5. Como adicionar uma nova consulta — passo a passo

Toda nova consulta exige tocar **3 arquivos** sempre na mesma ordem:

### Passo 1 — Escreva o SQL primeiro (no SSMS)

Antes de qualquer Python, valide a query no SSMS.
Regras do SQL Server que você DEVE seguir:

```sql
-- ✅ CORRETO
SELECT TOP 10 ...                          -- paginação usa TOP, nunca LIMIT
LTRIM(RTRIM(COLUNA))                       -- sempre limpar espaços
UPPER(coluna) LIKE UPPER(?)                -- case-insensitive sem ILIKE
CONVERT(date, ?, 103)                      -- converte DD/MM/YYYY para date
CAST(DATAAPONT AS DATE)                    -- remove hora de datetimeoffset
WHERE EMISSAO BETWEEN ? AND ?             -- EMISSAO já é type date, sem conversão

-- ❌ ERRADO
LIMIT 10                                   -- não existe no SQL Server
TRIM(coluna)                               -- não existe, use LTRIM(RTRIM())
coluna ILIKE ?                             -- não existe, use UPPER()+LIKE
%s                                         -- parâmetro do PostgreSQL, use ?
```

### Passo 2 — Crie ou edite o sql_service

Cada tabela tem seu próprio arquivo `sql_service_*.py`.
Se a sua query é de uma tabela nova, crie um arquivo novo.
Se é de uma tabela existente, adicione um método na classe existente.

**Estrutura padrão de um método:**

```python
def get_minha_consulta(self, data_inicio: str, data_fim: str) -> list[dict]:
    sql = """
        SELECT TOP 10
            LTRIM(RTRIM(COLUNA)) AS campo,
            SUM(VALOR)           AS total
        FROM dbo.MINHA_TABELA
        WHERE CAST(DATA AS DATE) BETWEEN CONVERT(date, ?, 103) AND CONVERT(date, ?, 103)
        GROUP BY LTRIM(RTRIM(COLUNA))
        ORDER BY total DESC
    """
    with get_mssql_conn() as conn:
        rows = conn.execute(sql, (data_inicio, data_fim)).fetchall()

    return [
        {"campo": row[0] or "", "total": float(row[1] or 0)}
        for row in rows
    ]
```

**Regras:**
- Sempre use `?` para parâmetros (nunca f-string com valores do usuário — SQL injection)
- Sempre converta `Decimal` para `float` no retorno
- Retorne `list[dict]` ou `dict` — nunca objetos pyodbc crus

### Passo 3 — Adicione o intent no interpreter.py

O interpretador usa regex. Você define:
1. Um padrão de texto (`_MEU_PATTERN = re.compile(...)`)
2. Uma regra de decisão no método `interpret()` que retorna `InterpretationResult`

**Onde colocar o padrão:** no bloco de atributos da classe, junto dos outros.

**Onde colocar a regra:** dentro do `interpret()`, em ordem de prioridade.
Regras mais específicas primeiro. Regras genéricas por último.

```python
# No bloco de atributos da classe RuleBasedInterpreter:
_MEU_PATTERN = re.compile(
    r"palavra1|palavra2|frase\s+especifica",
    re.IGNORECASE,
)

# No método interpret(), na posição certa:
if self._MEU_PATTERN.search(low):
    return InterpretationResult(
        intent="meu_intent",        # nome único, snake_case
        route="sql",                # "sql" ou "smalltalk"
        metric="minha_metrica",     # opcional, para debug
        entity_type="operador",     # opcional: "operador", "produto", "turno"
        entity_value=operador,      # valor extraído (ou None)
        data_inicio=ini,            # já extraído pelo _periodo_from_text()
        data_fim=fim,
        period_text=lbl,
        top_n=top_n or 5,
        confidence=0.90,            # 0.0 a 1.0 — quão certo você está
        reasoning="Descrição do que foi identificado.",
    )
```

**Sobre confidence:**
- `>= 0.87` → alta certeza, não herda período do histórico
- `0.75 – 0.87` → confiança média, pode herdar período
- `< 0.75` → baixa certeza, tenta carry-over do histórico
- `< 0.55` → fallback — vai para clarify/smalltalk

### Passo 4 — Adicione o dispatch no orchestrator.py

No método `_dispatch()`, adicione um bloco `if ir.intent == "meu_intent":`.

```python
if ir.intent == "meu_intent":
    rows = self.meu_service.get_minha_consulta(ini, fim)
    if not rows:
        return f"🔍 Nenhum dado encontrado{periodo}."
    header = f"📊 **Título da consulta**{periodo}\n\n"
    header += "| Campo | Total |\n|-------|-------|\n"
    linhas = "\n".join(
        f"| {r['campo']} | **{_fmt_kg(r['total'])}** |"
        for r in rows
    )
    return header + linhas
```

**Funções de formatação disponíveis:**

```python
_fmt_kg(valor)          # → "1.234,56 KG"
_posicao_label(pos)     # → "🥇" / "🥈" / "🥉" / "4°"
_periodo_label(ir)      # → " em Abril de 2026"
_origem_label(origem)   # → " [Entrada]"
```

**Variáveis já prontas no _dispatch():**

```python
ini       # data_inicio do InterpretationResult
fim       # data_fim
periodo   # texto formatado do período (ex: " em Abril de 2026")
top_n     # ir.top_n or 5
recursos  # ir.recursos (lista de códigos de extrusora, ou None)
is_diaria # True se ini == fim (consulta de um único dia)
```

---

## 6. Como testar sem reiniciar o serviço

O FastAPI em modo serviço (NSSM) requer restart para recarregar o código.
Mas você pode testar localmente antes:

```bash
# No terminal, dentro do venv:
cd ai_service_base/ai_service
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8001
```

Com `--reload`, o servidor reinicia sozinho a cada salvamento de arquivo.
Com `--port 8001`, não conflita com o serviço de produção na 8000.

Teste via curl ou Postman:
```json
POST http://localhost:8001/v1/chat/process
{
  "message": "Quem mais revisou esse mês?",
  "session_id": "teste-123",
  "user_name": "Pedro",
  "user_setor": "ti"
}
```

---

## 7. Quando o intent foi reconhecido errado

Se a Ayla responder algo estranho, olhe o campo `debug` na resposta da API:

```json
"debug": {
  "intent": "ranking_producao_geral",   ← o que o interpretador entendeu
  "route": "sql",
  "confidence": 0.82,
  "reasoning": "Ranking geral de produção.",
  "period_text": "Abril de 2026"
}
```

Com isso você sabe:
- Se o intent está errado → ajustar regex no `interpreter.py`
- Se o período está errado → verificar `_periodo_from_text()` no `interpreter.py`
- Se o SQL retornou vazio → testar a query direto no SSMS

---

## 8. Regras de negócio que nunca podem ser esquecidas

| Regra | Onde impacta |
|-------|-------------|
| Expedição NUNCA entra em rankings de produção | `sql_service_kardex.py`, `interpreter.py` |
| LD = `QUALIDADE = 'Y'` no KARDEX | `sql_service_kardex.py` |
| `EMISSAO` no KARDEX é `date` nativo — sem conversão | `sql_service_kardex.py` |
| Filtro por `origem` é OPCIONAL (muitos NULL) | todo sql_service |
| Parâmetro SQL Server = `?` (nunca `%s`) | todo sql_service |
| `TOP N` em vez de `LIMIT` | todo sql_service |
| `LTRIM(RTRIM())` em vez de `TRIM()` | todo sql_service |

---

## 9. Onde cada coisa está no banco

| Dado | Tabela | Serviço Python |
|------|--------|---------------|
| Produção extrusoras (KG, KGH, m/min) | `STG_PROD_SH6_VPLONAS` | `sql_service_sh6.py` |
| Qualidade / LD / expedição | `V_KARDEX` (view) | `sql_service_kardex.py` |
| Apontamentos de revisão de bobinas | `STG_APONT_REV_GERAL` | `sql_service_apont_rev.py` |
| Histórico de conversa | `mensagens` (PostgreSQL N8N) | `context_manager.py` |
| Intents da sessão | `session_intents` (PostgreSQL N8N) | `context_manager.py` |

---

## 10. Como adicionar um operador ou setor novo

Tudo em **`config.py`** — é a única fonte da verdade para operadores.

```python
SETORES: dict[str, list[str]] = {
    "revisao":   ["raul.araujo", "igor.chiva", "ezequiel.nunes", "kaua.chagas"],
    "expedicao": ["john.moraes", "rafael.paiva", ...],
    "extrusora": ["andreson.reis", ...],  # adicione aqui
}
```

Após adicionar em `config.py`, o interpretador já passa a reconhecer o nome automaticamente — ele usa `todos_operadores()` para extração.

---

## 11. Reiniciar o serviço em produção

Após fazer push no git, no servidor:

```bash
nssm restart ViniAI-CerebroIA
```

Ou via PowerShell no servidor:
```powershell
& 'C:\NSSM\nssm.exe' restart ViniAI-CerebroIA
```

Logs do serviço ficam em:
```
C:\Users\pedro.martins\Documents\ViniAi\logs\
```

---

## 12. Checklist para cada nova feature

- [ ] SQL testado no SSMS e retornando dados corretos
- [ ] Método criado no `sql_service_*.py` correto
- [ ] Intent e regex adicionados no `interpreter.py`
- [ ] Case adicionado no `_dispatch()` do `orchestrator.py`
- [ ] Se novo arquivo: import e instância no `__init__` do orquestrador
- [ ] Testado localmente com `uvicorn --reload`
- [ ] Commit com mensagem descritiva
- [ ] `nssm restart ViniAI-CerebroIA` no servidor
