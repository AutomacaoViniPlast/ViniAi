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
| `app/sql_service_kardex.py` | `Banco-De-Dados/SQLServer.md.md` |
| `app/sql_service_sh6.py` | `Banco-De-Dados/SQLServer.md.md` |
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

### dbo.STG_PROD_SH6_VPLONAS — apontamentos de produção (tabela ativa)
Tabela principal para consultas de produção das extrusoras.

| Coluna | Descrição |
|--------|-----------|
| FILIAL | 010101=VINIPLAST, 010201=Confecção |
| OP | Ordem de produção (gerada pelo PCP) |
| PRODUTO | Código do produto — primeiros 3 chars = tipo (ex: CLI, SUF) |
| RECURSO | 0003=Extrusora1/MAC1, 0007=Extrusora2/MAC2, 0005=Revisão, 0006=Revisão2 |
| NOME_USUARIO | Nome completo ou login do operador |
| DATA_APONT | Data do apontamento — usar para filtros **mensais** |
| DATA_INI | Data de início — usar para filtros **diários** |
| PESO_FILME_PASSADA | Peso produzido em KG |
| QTDPROD2 | Metros produzidos |
| MINUTOS | Minutos trabalhados |
| KGH | KG por hora (coluna direta — usar SUM(PESO)/( SUM(MINUTOS)/60 ) para calcular) |

**Regras de negócio SH6:**
- Produção mensal → `SUM(PESO_FILME_PASSADA)` filtrado por `DATA_APONT`
- Produção diária → `SUM(PESO_FILME_PASSADA)` filtrado por `DATA_INI`
- Metros/min → `SUM(QTDPROD2) / SUM(MINUTOS)`
- KGH → `SUM(PESO_FILME_PASSADA) / (SUM(MINUTOS) / 60)`
- Filial padrão → `010101` quando não especificada
- Recurso padrão → `('0003', '0007')` — exclui REVISA automaticamente
- Recurso REVISA → ignorar por enquanto

### dbo.V_KARDEX — view de movimentação de materiais (implementada em sql_service_kardex.py)
Representa movimentações industriais: produção, revisão e movimentação interna.
Consultada quando o request envolver: OP, TURNO, TES, qualidade Y/I, LOTE ou detalhamento de movimentação.

| Coluna | Descrição |
|--------|-----------|
| FILIAL | 010101=VINIPLAST, 010201=VINITRADE INDUSTRIA E COMERCIO LTDA |
| ORIGEM | SD1, SD2, SD3 — filtro opcional |
| EMISSAO | date — campo principal de filtro por período |
| TES | 499=entrada, 999=saída, 502=inconsistência XML. TES 010 existe mas está bloqueada (pendente mapeamento) |
| PRODUTO | código do produto — ver parse_produto() em sql_service_kardex.py |
| DESCRICAO | descrição completa do material |
| LOTE | sequência gerada ao lançar bobina na produção |
| QUANTIDADE | total produzido/movimentado. TES 999 retorna valores negativos — **PENDENTE: confirmar lógica de sinal** |
| USUARIO | operador que registrou o movimento |
| LOCAL_OP | localização: 'EXTRUSAO'=produção ativa. **PENDENTE: mapear outros valores** |
| TURNO | turno — filtrar somente quando explicitamente solicitado |
| RECURSO | 0003=Extrusora1/MAC1, 0007=Extrusora2/MAC2 |
| QUALIDADE | Y=LD, I=Inteiro (equivalente à posição 5 do código PRODUTO) |

**Regras de negócio V_KARDEX:**
- Filial padrão → `010101` quando não especificada
- LOCAL_OP → sempre filtrar por `'EXTRUSAO'` em consultas de produção/soma
- TURNO → NÃO filtrar salvo solicitação explícita do usuário
- TES 010 → bloqueada no código — não exposta nem via solicitação direta
- QUANTIDADE negativa (TES 999) → lógica de saldo PENDENTE de confirmação
- parse_produto(): pos 1-3=código-base, pos 5=Y/I, pos 6-8=cor1, pos 11-13=cor2

**Roteamento V_KARDEX vs SH6 (CONFIRMADO — REGRA FIXA):**
- **V_KARDEX** → qualquer consulta que envolva qualidade do material:
  - LD (Y), Inteiro (I), Fora de Padrão (P)
  - "por qualidade", "qualidade da produção", "diferenciar LD e Inteiro"
  - Resposta SEMPRE exibe breakdown: Inteiro + LD + FP + Total
- **SH6** → consultas sem contexto de qualidade:
  - Produção por operador (ex: "produção do Ezequiel em março")
  - Produção por período (ex: "produção de ontem", "de janeiro até hoje")
  - Extrusora (KGH, m/min, comparativo MAC1 vs MAC2, horas trabalhadas)
  - Rankings de produção por peso (sem qualidade)
- **Regra de desempate:** se houver dúvida, verificar se a consulta menciona Y/I/P, LD, Inteiro, FP → V_KARDEX. Caso contrário → SH6.

### dbo.STG_PROD_SD3 — movimentação interna
### dbo.STG_APONT_REV_GERAL — apontamentos de revisão (pendente mapeamento)

## Recursos de produção (extrusoras)
- Extrusora 1 / MAC 1 → recurso `0003`
- Extrusora 2 / MAC 2 → recurso `0007`
- Revisão → recursos `0005` e `0006`

## Estrutura do código do produto
Exemplo: CLILA0600L0400A
- CLI → tipo de produto (posições 1-3) — tabela de tipos pendente
- Posição 5: Y=LD, I=Inteiro (válido para V_KARDEX e SH6)
- No V_KARDEX, campo `QUALIDADE` já contém esse valor pré-calculado
- Função `parse_produto()` em sql_service_kardex.py extrai: codigo_base, tipo_material, cor_1, cor_2

## Conceitos de negócio (IMPORTANTE — não confundir)
- Produção   = material fabricado nas extrusoras (MAC1/MAC2). Recursos 0003 e 0007.
- Revisão    = inspeção do material já produzido. Recursos 0005 e 0006. Identifica LD (Y) ou Inteiro (I).
- Expedição  = liberação de bobinas para clientes. NUNCA entra em rankings de produção.

## Setores e operadores (arquivo: app/config.py — fonte da verdade)
Produção (extrusora):  pendente — documentação sendo preparada pelo usuário
Revisão:   raul.araujo, igor.chiva, ezequiel.nunes, kaua.chagas
Expedição: john.moraes, rafael.paiva, andre.prado, richard.santos, arilson.aguiar
OPERADORES_ATIVOS (escopo padrão): ezequiel.nunes, raul.araujo, kaua.chagas, igor.chiva

> kaua.chagas: setor produção na empresa, mas operacionalmente atua na revisão — listado em revisao no config.py.

## Estrutura de arquivos
app/config.py              → setores, operadores e tipos de origem (fonte da verdade)
app/db.py                  → get_mssql_conn() SQL Server + get_n8n_conn() PostgreSQL N8N
app/sql_service_kardex.py  → queries dbo.V_KARDEX (LD, TES, TURNO, LOTE, qualidade Y/I)
app/sql_service_sh6.py     → queries STG_PROD_SH6_VPLONAS (produção extrusoras — ativo)
app/orchestrator.py    → lógica principal: RAG, period-inherit, auto-inject, roteamento
app/interpreter.py     → regras regex de intent + parsing de períodos
app/llm_handler.py     → ChatGPT com date.today() injetado no system_prompt
app/context_manager.py → leitura do histórico no banco N8N (somente leitura)
app/agents.py          → registro de agentes (nome, domínio, system_prompt, capabilities)
app/permissions.py     → controle de acesso por departamento + mensagem LGPD
app/schemas.py         → modelos Pydantic
app/main.py            → FastAPI entry point com CORS

## Regra anti circular import
config / db / permissions / agents → sem dependências internas
sql_service_kardex / sql_service_sh6 → importa db
interpreter    → importa config, schemas
context_manager → importa db, schemas
llm_handler    → importa schemas
orchestrator   → importa tudo acima
main           → importa orchestrator, schemas

## Regras de query (SQL Server — pyodbc)
- Sempre usar LTRIM(RTRIM(campo)) para remover espaços
- Parâmetros com ? (pyodbc), NÃO %s
- Case-insensitive: LOWER(col) LIKE LOWER(?)
- Paginação: TOP N (não LIMIT)
- Filtro por origem é OPCIONAL (muitos registros têm NULL)
- EMISSAO (STG_KARDEX) é tipo date nativo — sem conversão de texto

## Pendências técnicas
- Identificar e mapear colunas de dbo.STG_APONT_REV_GERAL
- Cadastrar operadores do setor produção (extrusora) em config.py — aguardando documentação
- Integrar STG_PROD_SH6 e STG_PROD_SD3 quando os novos agentes forem criados
- Comparação entre períodos (intent comparacao_periodos)
- Novos agentes: Iris (PCP), Maya (Controladoria), Nina (RH), Eva (Vendas)
- Tabela de tipos de produto (3 primeiros chars: CLI, SUF, etc.)
- **V_KARDEX — LOCAL_OP:** mapear outros valores além de 'EXTRUSAO' (usuario explicará)
- **V_KARDEX — QUANTIDADE negativa (TES 999):** confirmar lógica de sinal e tratamento de saldo
- **V_KARDEX — Roteamento:** confirmar regra completa de quando usar V_KARDEX vs SH6 (quando envolver OP, TURNO, TES, Y/I, LOTE — mas aguardar confirmação final)
- Integrar sql_service_kardex.py no orchestrator após confirmação do roteamento

## Regras de colaboração (OBRIGATÓRIO)
- **Sempre perguntar ao usuário antes de codificar** quando houver qualquer dúvida
- Sistema disponível somente para gestores — não para operadores
- Commits sempre ao final de sessão com mensagem descritiva em português
- CLAUDE.md não sobe para o git (está no .gitignore)

## Protocolo Codex + Claude Code (OBRIGATÓRIO)

Quando Codex e Claude Code atuarem no mesmo projeto, os dois devem trabalhar como revisão cruzada e não como fontes independentes de verdade.

### Fonte de verdade
- Código atual do workspace sempre vence memória antiga
- `app/config.py` é a fonte de verdade para operadores, setores e origens
- `CLAUDE.md` é resumo operacional do agente
- `project_memory/ViniAI-Memoria/` é memória longa e deve refletir o código real

### Regra de validação cruzada
- Antes de afirmar regra de negócio, conferir no código e na tabela/serviço corretos
- Antes de editar roteamento, conferir `interpreter.py`, `orchestrator.py` e o `sql_service_*` envolvido
- Se um agente encontrar inconsistência entre documentação e código, deve corrigir a documentação e registrar a divergência
- Se uma resposta depender de hipótese não confirmada, isso deve ser dito explicitamente

### Como corrigir erro do outro agente
- Não assumir que a resposta anterior está correta só porque foi dada por outro agente
- Revalidar a intenção, a tabela consultada, os filtros aplicados e o período interpretado
- Ao corrigir um erro anterior, registrar claramente:
  1. qual era o comportamento errado
  2. qual é a regra correta
  3. em quais arquivos a correção foi feita
- Se a correção não puder ser validada no banco real, deixar isso explícito

### Handoff entre agentes
- Ao encerrar uma sessão, deixar no vault e no `CLAUDE.md` apenas fatos validados
- Sempre que alterar regra de roteamento, atualizar a nota correspondente no vault
- Sempre que detectar bug relevante, registrar também em `RunBooks/Pendencias.md.md` ou remover de lá se foi resolvido
- O próximo agente deve começar lendo `Hub/Home.md.md` e depois apenas as notas relacionadas ao arquivo alterado

### Objetivo da colaboração
- Reduzir alucinação
- Evitar repetir erro já cometido
- Garantir que interpretação, roteamento e SQL estejam alinhados
- Fazer revisão mútua de contexto antes de qualquer mudança sensível

## Checklist obrigatório antes de encerrar qualquer sessão de desenvolvimento

Antes de considerar a sessão encerrada, verificar e executar cada item:

- [ ] **Vault Obsidian atualizado** — para cada arquivo `.py` modificado, atualizar a nota correspondente conforme tabela acima. Não deixar para a próxima sessão.
- [ ] **Commit feito** — com mensagem descritiva em português resumindo tudo que foi implementado.
- [ ] **CLAUDE.md atualizado** — se novos arquivos, regras de negócio ou pendências surgiram.
- [ ] **Pendências registradas** — qualquer item que ficou em aberto deve estar documentado nas pendências técnicas do CLAUDE.md e/ou em `RunBooks/Pendencias.md.md`.

> **Regra:** o vault deve refletir o estado atual do código. Se o código mudou e o vault não foi atualizado, a sessão não está encerrada.

<!-- SYNC_MEMORY:START -->

## Contexto Auto-Atualizado — Última Sessão
> Gerado em 2026-04-23 10:49 por `scripts/sync_memory.py`

**Ultimos commits:**
- Fix: adiciona handler producao_por_turno e simplifica capabilities para Qualidade+Extrusora (2026-04-23)
- Feat: V_KARDEX retorna breakdown completo de qualidade (Inteiro + LD + FP + Total) (2026-04-23)
- Fix: reconhece data DD/MM/YYYY no parser de período e retorna total da fábrica quando sem operador (2026-04-23)

**Arquivos alterados nesta sessao:**
- `CLAUDE.md`

**Pendencias criticas (de `RunBooks/Pendencias.md.md`):**
- `kaua.chagas` ausente no setor `producao`
- **Valores incorretos nas queries de LD (KARDEX)**

<!-- SYNC_MEMORY:END -->
