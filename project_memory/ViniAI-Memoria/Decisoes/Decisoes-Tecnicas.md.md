# Decisões Técnicas

> Registro de escolhas arquiteturais e de implementação com o contexto de por que foram feitas.
> Essas decisões não devem ser revertidas sem revisão consciente do motivo original.

---

## 1. SQL Server para dados industriais (separado do PostgreSQL)

**Decisão:** Migrar dados industriais do PostgreSQL para o SQL Server METABASE existente.

**Por quê:**
- Os dados industriais já viviam no SQL Server (Metabase) — a migração foi de volta à fonte original
- SQL Server tem integração nativa com os sistemas de fábrica (TOTVS, coletores, etc.)
- Elimina duplicidade de dados e sincronização entre bancos
- A separação de responsabilidades (SQL Server = industrial / PostgreSQL = conversas) torna o sistema mais claro e seguro

**Impacto:**
- `app/db.py` tem dois context managers: `get_mssql_conn()` e `get_n8n_conn()`
- Requer ODBC Driver 17 instalado no Windows Server
- Parâmetros pyodbc usam `?` em vez de `%s`

---

## 2. Interpretador por regras em vez de LLM

**Decisão:** Classificar intenções com 19 regras de regex, sem chamar API de LLM.

**Por quê:**
- Determinístico — auditável, testável, sem surpresas
- Custo zero de tokens para as perguntas mais frequentes (consultas de dados)
- Latência próxima de zero para classificação
- Regras são fáceis de ajustar sem re-treinar modelo
- O ChatGPT só é chamado para conversação natural (smalltalk/clarify) — menos de 20% dos requests

**Trade-off:**
- Precisa de manutenção manual quando surgem novas formas de perguntar
- Não generaliza tão bem para variações muito criativas de linguagem
- Solução de longo prazo: substituir por LLM com function calling mantendo a interface `InterpretationResult`

---

## 3. Histórico de conversa no PostgreSQL (stateless FastAPI)

**Decisão:** FastAPI não mantém estado em memória — todo contexto vem do banco a cada request.

**Por quê:**
- Permite escalar o AI Service horizontalmente sem sessões "presas" em uma instância
- O Backend Node.js, que já gerencia usuários, centraliza também o salvamento das mensagens
- Facilita debugging: o histórico completo está no banco, consultável diretamente

**Consequência:**
- Cada request lê 16 mensagens do PostgreSQL antes de processar
- O FastAPI faz somente leitura do banco de histórico

---

## 4. Período padrão = mês atual dinâmico

**Decisão:** Quando nenhum período é mencionado, usar o mês atual em vez de um intervalo fixo.

**Por quê:**
- O intervalo fixo anterior (`01/01/2025 a 31/12/2026`) retornava anos de dados para perguntas simples como "quem gerou mais LD?"
- O usuário normalmente quer dados recentes — o mês atual é o default mais intuitivo
- Pode ser explicitado quando necessário ("em 2025", "este ano")

---

## 5. Date injection no LLM

**Decisão:** Injetar `date.today()` no topo do system prompt em toda chamada ao ChatGPT.

**Por quê:**
- O ChatGPT (gpt-4o-mini) não tem acesso ao relógio — sem injeção, inventa datas
- Responses com "em 2024" ou "no ano passado" (quando era 2026) eram frequentes antes da correção
- A data é injetada dinamicamente a cada chamada para refletir o dia real

---

## 6. Guard de dados na regra de smalltalk longa

**Decisão:** Se a mensagem contém LD/produção/expedição, não direcionar ao LLM mesmo que pareça conversacional.

**Por quê:**
- Padrões conversacionais expandidos (ex: "me fale sobre", "pode me dizer") poderiam interceptar consultas de dados reais
- O LLM responderia "não tenho esse dado" em vez de buscar no banco
- A guarda garante que frases como "me fale sobre o LD de janeiro" sempre vão ao SQL

---

## 7. Separação de serviços: Frontend / Backend / AI Service

**Decisão:** Três processos independentes em vez de monolito.

**Por quê:**
- Permite reiniciar o AI Service (Python) sem derrubar autenticação e histórico (Node.js)
- Deploy de frontend separado (só rebuild do React, sem tocar na IA)
- Possibilidade futura de escalar o AI Service independentemente
- Linguagens adequadas para cada papel: Python para IA/ML, Node.js para API REST/JWT, React para UI

---

## Links relacionados

- [[Arquitetura-Geral]] — resultado das decisões
- [[Interpretacao-de-Intencao]] — decisão 2 em prática
- [[RAG-Conversacional]] — decisões 3, 5 e 6 em prática
- [[Pendencias]] — o que ainda precisa ser resolvido
