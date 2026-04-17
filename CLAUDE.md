# ViniAI — Contexto do projeto

## Memória do Projeto — Vault Obsidian

**Caminho:** `project_memory/ViniAI-Memoria/`

**Ao iniciar qualquer sessão:** leia `project_memory/ViniAI-Memoria/Hub/Home.md.md` para ter o mapa do vault e decidir quais notas são relevantes para a tarefa.

**Após mudanças de código, atualize a nota correspondente no vault:**

| Se mudou... | Atualizar nota |
|-------------|---------------|
| `app/interpreter.py` | `Intencao/Interpretacao-de-Intencao.md.md` |
| `app/orchestrator.py` | `RAG/RAG-Conversacional.md.md` |
| `app/agents.py` | `Arquitetura/Agentes.md.md` |
| `app/config.py` | `Arquitetura/Agentes.md.md` + `Banco-De-Dados/SQLServer.md.md` |
| `app/permissions.py` | `Integrações/Claude-Code.md.md` |
| `app/sql_service.py` | `Banco-De-Dados/SQLServer.md.md` |
| `app/db.py` | `Banco-De-Dados/SQLServer.md.md` + `Banco-De-Dados/PostgreSQL.md.md` |
| Nova pendência resolvida | `RunBooks/Pendencias.md.md` |
| Decisão arquitetural tomada | `Decisoes/Decisoes-Tecnicas.md.md` |

**Regra geral:** sempre que fizer commit, verifique se alguma nota do vault precisa ser atualizada para refletir o estado atual do código.

---

## O que é
IA de consulta de produção fabril. Backend FastAPI (Python) + SQL Server (dados industriais) + PostgreSQL (histórico de conversas).

## Stack
- FastAPI rodando em localhost:8000
- **SQL Server** em 192.168.1.83:50172 — banco METABASE — **exclusivo para consultas de dados industriais**
- **PostgreSQL N8N** em 192.168.1.85:5432 — **exclusivo para autenticação de usuário, conversas e mensagens**
- Conexão SQL Server via pyodbc (ODBC Driver 17 for SQL Server)

## Separação de responsabilidades dos bancos (REGRA FIXA)
- **SQL Server (METABASE):** SOMENTE dados industriais — produção, kardex, revisão, expedição
- **PostgreSQL (N8N):** SOMENTE autenticação de usuário, histórico de conversas e mensagens
- Nenhum dado industrial vai ao PostgreSQL. Nenhum dado de autenticação/conversa vai ao SQL Server.

## Tabelas SQL Server — METABASE

### dbo.STG_KARDEX — tabela principal (mais completa)
Abrange todo o ciclo industrial:
- **Matéria-prima**: entrada de CARBONATO, RESINA, DRAPEX, DOP
- **Produção**: 1ª, 2ª e 3ª passada do filme plástico (extrusora)
- **Revisão**: inspeção das bobinas — identificação de defeitos por metro

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| USUARIO | varchar(25) | Login do operador — usar LTRIM(RTRIM()) |
| EMISSAO | date | Data nativa SQL Server — sem conversão |
| PRODUTO | varchar(15) | Código do produto (posição 5 = Y ou I) |
| QUALIDADE | varchar(1) | Y=LD (defeito), I=Inteiro (sem defeito) |
| TOTAL | float | Quantidade em KG |
| TURNO | varchar(5) | Turno de produção |
| ORIGEM | varchar(3) | SD1=Entrada, SD2=Saída, SD3=Mov. Interna |

### dbo.STG_PROD_SH6 (ou STG_PROD_SH6_VPLONAS) — apontamentos de produção
Focada em produção. Aborda movimentações internas com detalhes operacionais como horas trabalhadas, KG/hora e motivo do defeito LD (coluna MOTIVO_Y).

### dbo.STG_PROD_SD3 — movimentação interna
Tabela de movimentação interna da empresa (produção de bobinas). Contém tipos de movimento (TM: 010, 100, 499, 502, 999) e motivos de perda.

### dbo.STG_APONT_REV_GERAL — apontamentos de revisão geral
**Pendente de identificação** — tabela identificada como existente no banco, ainda sem análise completa das colunas e uso. Provavelmente relacionada a apontamentos do setor de Revisão.

> A tabela mais completa para análise de produção e revisão é a **STG_KARDEX**.
> As demais tabelas serão integradas conforme os novos agentes e funcionalidades forem desenvolvidos.

## Estrutura do código do produto
Exemplo: TD2AYBR1BOBR100
- TD2 → tipo de material (posições 1-3)
- A   → variante (posição 4)
- Y   → indicador de qualidade (posição 5): **Y=LD (defeito)**, **I=Inteiro (sem defeito)**
- BR1 → código de cor (branco)
- BO  → tipo de tecido/acabamento (blackout)
- BR100 → dimensão/tamanho

> No SQL Server, o campo `QUALIDADE` já contém esse valor pré-calculado ('Y' ou 'I').
> A posição 5 do produto e o campo QUALIDADE são equivalentes — usar `QUALIDADE = 'Y'` nas queries.

## Conceitos de negócio (IMPORTANTE — não confundir)
- Produção   = material que saiu da extrusora. Operadores de produção NÃO incluem expedição.
- Revisão    = inspeção do material após extrusão. Identifica defeito (LD = Y) ou inteiro (I).
               Os números da revisão representam o que foi inspecionado, NÃO produzido.
- Expedição  = liberação de bobinas para clientes. NÃO produzem — apenas movimentam.
               NUNCA entram em rankings de produção (excluídos automaticamente).

## Setores e operadores (arquivo: app/config.py — fonte da verdade)
Produção:  (em cadastramento — lista vazia)
Revisão:   raul.araujo, igor.chiva, ezequiel.nunes
Expedição: john.moraes, rafael.paiva, andre.prado, richard.santos, arilson.aguiar
OPERADORES_ATIVOS (escopo padrão): ezequiel.nunes, raul.araujo, kaua.chagas, igor.chiva

## Estrutura de arquivos
app/config.py       → setores, operadores e tipos de origem (fonte da verdade)
app/db.py           → get_mssql_conn() SQL Server + get_n8n_conn() PostgreSQL N8N
app/sql_service.py  → queries SQL Server contra dbo.STG_KARDEX
app/orchestrator.py → lógica principal: RAG, period-inherit, auto-inject, roteamento
app/interpreter.py  → 19 regras regex de intent + parsing de períodos
app/llm_handler.py  → ChatGPT com date.today() injetado no system_prompt
app/context_manager.py → leitura do histórico no banco N8N (somente leitura)
app/agents.py       → registro de agentes (nome, domínio, system_prompt, capabilities)
app/permissions.py  → controle de acesso por departamento + mensagem LGPD
app/schemas.py      → modelos Pydantic
app/main.py         → FastAPI entry point com CORS

## Regra anti circular import
config / db / permissions / agents → sem dependências internas
sql_service    → importa db
interpreter    → importa config, schemas
context_manager → importa db, schemas
llm_handler    → importa schemas
orchestrator   → importa tudo acima
main           → importa orchestrator, schemas

## Regras de query (SQL Server — pyodbc)
- Sempre usar LTRIM(RTRIM(USUARIO)) para remover espaços
- Parâmetros com ? (pyodbc), NÃO %s
- Case-insensitive: LOWER(col) LIKE LOWER(?)
- Paginação: TOP N (não LIMIT)
- Filtro por origem é OPCIONAL (muitos registros têm NULL)
- LD = QUALIDADE = 'Y' (não usar SUBSTRING — já pré-calculado)
- EMISSAO é tipo date nativo — sem conversão de texto

## Pendências técnicas
- Identificar e mapear colunas de dbo.STG_APONT_REV_GERAL
- Adicionar kaua.chagas ao setor producao em config.py
- Integrar STG_PROD_SH6 e STG_PROD_SD3 quando os novos agentes forem criados
- Comparação entre períodos (intent comparacao_periodos)
- Novos agentes: Iris (PCP), Maya (Controladoria), Nina (RH), Eva (Vendas)
- Suporte a queries cruzadas entre tabelas (ex: KARDEX + SH6 para análise completa)

<!-- SYNC_MEMORY:START -->

## Contexto Auto-Atualizado — Última Sessão
> Gerado em 2026-04-17 12:12 por `scripts/sync_memory.py`

**Ultimos commits:**
- Feat: sistema de memória persistente com Obsidian e auto-sync (2026-04-17)
- Feat: conversação humanizada da Ayla — saudações proativas e guard de dados (2026-04-16)
- Melhoria na interpretação (2026-04-16)

**Pendencias criticas (de `RunBooks/Pendencias.md.md`):**
- `kaua.chagas` ausente no setor `producao`

<!-- SYNC_MEMORY:END -->
