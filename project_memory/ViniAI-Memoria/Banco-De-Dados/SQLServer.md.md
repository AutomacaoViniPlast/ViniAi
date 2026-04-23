# SQL Server — METABASE

## Conexão

| Campo           | Valor                                                                                  |
| --------------- | -------------------------------------------------------------------------------------- |
| Host            | 192.168.1.83                                                                           |
| Porta           | 50172                                                                                  |
| Banco           | METABASE                                                                               |
| Usuário         | sa                                                                                     |
| Driver          | ODBC Driver 17 for SQL Server                                                          |
| Variável `.env` | `MSSQL_HOST`, `MSSQL_PORT`, `MSSQL_DB`, `MSSQL_USER`, `MSSQL_PASSWORD`, `MSSQL_DRIVER` |

> [!warning] Uso exclusivo
> Este banco é usado **SOMENTE** para consultas de dados industriais.
> Nenhum dado de autenticação, conversa ou usuário vai aqui.

---

## Arquivos de Serviço

| Arquivo | Tabela/View | Quando usar |
|---------|-------------|-------------|
| `app/sql_service_sh6.py` | `dbo.STG_PROD_SH6_VPLONAS` | Consultas **sem** qualidade do material (KGH, m/min, ranking de peso, horas) |
| `app/sql_service_kardex.py` | `dbo.V_KARDEX` | Consultas **com** qualidade do material (Y=LD, I=Inteiro, P=Fora de Padrão) |

---

## Tabelas / Views

### dbo.STG_PROD_SH6_VPLONAS — apontamentos de produção (ativa)

Tabela principal para consultas de produção das extrusoras MAC1 e MAC2.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| FILIAL | varchar | 010101=VINIPLAST, 010201=Confecção |
| OP | varchar | Ordem de produção (gerada pelo PCP) |
| PRODUTO | varchar | Código do produto — primeiros 3 chars = tipo |
| RECURSO | varchar | 0003=Extrusora1/MAC1, 0007=Extrusora2/MAC2, 0005=Revisão, 0006=Revisão2 |
| NOME_USUARIO | varchar | Nome completo ou login do operador |
| DATA_APONT | date | Data do apontamento — usar para filtros **mensais** |
| DATA_INI | date | Data de início — usar para filtros **diários** |
| PESO_FILME_PASSADA | float | Peso produzido em KG |
| QTDPROD2 | float | Metros produzidos |
| MINUTOS | float | Minutos trabalhados |
| KGH | float | Coluna direta — NÃO usar diretamente, calcular via fórmula |

**Regras de negócio SH6:**
- Produção mensal → `SUM(PESO_FILME_PASSADA)` filtrado por `DATA_APONT`
- Produção diária → `SUM(PESO_FILME_PASSADA)` filtrado por `DATA_INI` (quando ini == fim)
- Metros/min → `SUM(QTDPROD2) / SUM(MINUTOS)`
- KGH → `SUM(PESO_FILME_PASSADA) / (SUM(MINUTOS) / 60)` — nunca AVG(KGH)
- Filial padrão → `010101` quando não especificada
- Recurso padrão → `('0003', '0007')` — exclui Revisão automaticamente
- Cobertura temporal disponível → `get_periodos_disponiveis()` agrupa `DATA_APONT`
  por ano/mês para responder perguntas como `quais meses você tem dados?`
- Produção dia a dia → `get_producao_por_dia()` agrupa `DATA_INI` por data
  para intervalos como `01/04 até 08/04`

---

### dbo.V_KARDEX — view de movimentação de materiais

Representa movimentações industriais: produção, revisão e movimentação interna.
Implementada em `app/sql_service_kardex.py`.

**Roteamento (REGRA FIXA — confirmada com usuário 2026-04-23):**
- **Usar V_KARDEX** sempre que a consulta mencionar qualidade do material: LD (Y), Inteiro (I), Fora de Padrão (P), "por qualidade", "diferenciar LD e Inteiro", "qualidade da produção"
- **Usar SH6** para produção sem contexto de qualidade: por operador, por período, extrusora, KGH, m/min, horas trabalhadas
- **Resposta V_KARDEX** SEMPRE exibe breakdown: Inteiro + LD + FP + Total geral
- **Desempate:** se mencionou Y/I/P, LD, Inteiro ou FP → V_KARDEX; caso contrário → SH6

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| FILIAL | varchar | 010101=VINIPLAST, 010201=MKTRADING |
| ORIGEM | varchar | SD1=Entrada (NF entrada), SD2=Saída (NF saída), SD3=Movimentação Interna (sem NF) |
| OP | varchar | Ordem de Produção (gerada pelo PCP) |
| EMISSAO | date | Data de emissão — campo principal de filtro por período |
| LOCAL | varchar | Armazém — valores: 01, 10, 12, 15, 20, 35, 40, 50, 60. **Significados pendentes de mapeamento** |
| TES | varchar | Tipo de movimentação (ver mapa abaixo) — **PENDENTE: detalhamento completo** |
| PRODUTO | varchar | Código do produto — ver parse_produto() |
| DESCRICAO | varchar | Descrição completa do material |
| TIPO | varchar | **PENDENTE: sem regra definida ainda** |
| UM | varchar | Unidade de medida principal: `KG` \| `MT` — sempre lida junto com QUANTIDADE |
| LOTE | varchar | Sequência gerada ao registrar bobina na produção |
| QUANTIDADE | float | Total produzido/movimentado — **sempre ler com UM, nunca somar KG com MT** |
| USUARIO | varchar | Operador que registrou o movimento |
| LOCAL_OP | varchar | Localização operacional: `EXTRUSAO`=produção. **Outros valores pendentes de mapeamento** |
| FAMILIA | varchar | Família do produto (3 primeiros chars de PRODUTO) — coluna direta, usar com prioridade |
| COR_FRENTE | varchar | Cor frente — **prioritária sobre inferência do parser** |
| COR_MEIO | varchar | Cor meio — **prioritária sobre inferência do parser** |
| COR_VERSO | varchar | Cor verso — **prioritária sobre inferência do parser** |
| TURNO | varchar | Turno — filtrar somente quando explicitamente solicitado |
| HORA | varchar | Hora do apontamento |
| QTSEGUM | float | Segunda quantidade — unidade determinada por qualidade (ver regra abaixo) |
| RECURSO | varchar | 0003=Extrusora1/MAC1, 0007=Extrusora2/MAC2 |
| QUALIDADE | varchar | Y=LD, I=Inteiro, P=Fora de Padrão (equivalente à posição 5 do PRODUTO) |
| USR_LIB_APO | varchar | Usuário que libera o apontamento quando o lançamento está bloqueado |

**Mapa de TES:**

| Código | Significado |
|--------|-------------|
| `499` | Movimentação interna de entrada (entrada de estoque) |
| `999` | Movimentação interna de saída |
| `502` | Inconsistência XML (CNPJ, IE, Data, Modelo, Série, Número ou Tipo Emissão) |
| `010` | **Bloqueada no código** — significado pendente de mapeamento |

**Mapa de QUALIDADE:**

| Código | Significado |
|--------|-------------|
| `Y` | LD / Leves Defeitos |
| `I` | Inteiro |
| `P` | Fora de Padrão |
| `BAG` | BAG (produto especial MSP008 — não segue leitura posicional) |

**Regra de QTSEGUM por qualidade** (exclusiva para esta coluna):

| Qualidade | Unidade de QTSEGUM |
|-----------|-------------------|
| I / P | KG |
| Y / BAG | MT |

**Regras de negócio V_KARDEX:**
- Filial padrão → `010101`
- LOCAL_OP → sempre filtrar por `'EXTRUSAO'` em consultas de produção/soma
- TURNO → NÃO filtrar salvo solicitação explícita do usuário
- TES 010 → bloqueada — não exposta mesmo se solicitada
- QUANTIDADE → retornada separada por UM em todos os agregados: `{"KG": ..., "MT": ...}`
- FAMILIA → usar coluna direta da view; fallback para `parse_produto()["familia"]`
- COR_FRENTE/MEIO/VERSO → usar colunas diretas; parser fornece apenas inferência de fallback
- `parse_produto()`: trata MSP008 como BAG, pos 1-3=família, pos 5=Y/I/P, pos 6-8=cor_frente inferida, pos 11-13=cor_verso inferida

**Método `get_resumo_qualidade(ini, fim, operador?, filtro_usuarios?)` — IMPLEMENTADO:**
Retorna breakdown por QUALIDADE: `{"I": {"KG": ..., "MT": ...}, "Y": {...}, "P": {...}}`
Usado pelo orchestrator para exibir: Inteiro + LD + FP + Total na mesma resposta.

**Método `get_periodos_disponiveis(filial?, filtro_usuarios?)` — IMPLEMENTADO:**
Agrupa `EMISSAO` por ano/mês e é usado para cobertura temporal da base de
Qualidade / Revisão.

> [!warning] Pendências V_KARDEX
> - LOCAL: mapear significado de cada armazém (01, 10, 12, 15, 20, 35, 40, 50, 60)
> - LOCAL_OP: mapear outros valores além de 'EXTRUSAO'
> - TIPO: sem regra de negócio definida ainda
> - TES: detalhamento completo pendente
> - QUANTIDADE negativa (TES 999): confirmar lógica de saldo antes de implementar somatórios mistos
> - **CRÍTICO:** QUANTIDADE pode ser coluna errada para LD (Y) — usuário irá confirmar coluna correta (pode ser QTSEGUM)

---

### dbo.STG_PROD_SD3 — movimentação interna
Pendente de integração.

### dbo.STG_APONT_REV_GERAL — apontamentos de revisão
Pendente de mapeamento de colunas.

---

## Estrutura do Código de Produto

```
Exemplo: CLILA0600L0400A
  CLI   → código-base do produto (pos 1-3) — tabela de tipos pendente
  L     → variante (pos 4)
  A     → qualidade (pos 5): Y=LD, I=Inteiro
  0600  → cor 1 (pos 6-8 + extra)
  L     → separador
  0400  → cor 2 (pos 11-13 + extra)
  A     → sufixo
```

Função `parse_produto()` em `sql_service_kardex.py` retorna: `codigo_produto_original`, `familia`, `qualidade_material`, `qualidade_descricao`, `posicao_5_raw`, `cor_frente_inferida`, `cor_meio_inferida`, `cor_verso_inferida`, `is_bag`.

Caso especial: `MSP008` → retorna `is_bag=True`, `qualidade_material="BAG"` sem leitura posicional.

---

## Regras de Query (pyodbc)

```sql
-- Sempre limpar espaços
LTRIM(RTRIM(USUARIO))

-- Parâmetros: usar ? (pyodbc), NUNCA %s
WHERE EMISSAO BETWEEN ? AND ?

-- Case-insensitive
LOWER(col) LIKE LOWER(?)
-- ou UPPER(col) para LOCAL_OP

-- Paginação: TOP N, nunca LIMIT
SELECT TOP 5 ...

-- Datas: tipos date nativos — sem conversão de texto
-- Python: datetime.strptime(date_str, "%d/%m/%Y").date()

-- Filtro por ORIGEM é sempre opcional (muitos registros têm NULL)
```

---

## Conceitos de Negócio

> [!warning] Não confundir
> - **Produção** = material que saiu da extrusora (recursos 0003 e 0007)
> - **Revisão** = inspeção do material após extrusão. Recursos 0005 e 0006. Identifica LD (Y) ou Inteiro (I)
> - **Expedição** = liberação de bobinas para clientes. **NUNCA** entra em ranking de produção

---

## Links relacionados

- [[Arquitetura-Geral]] — contexto do banco na arquitetura
- [[Agentes]] — quem consulta este banco
- [[Interpretacao-de-Intencao]] — como as queries são geradas
