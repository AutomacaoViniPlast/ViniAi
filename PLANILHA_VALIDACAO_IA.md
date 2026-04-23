# Planilha de Validacao da IA

## Objetivo

Este arquivo serve como checklist para validar se a Ayla:

- interpreta a pergunta corretamente
- consulta a tabela certa
- aplica o periodo certo
- usa o filtro certo
- responde no formato esperado

## Como usar

Para cada pergunta:

1. Envie exatamente o texto sugerido
2. Verifique se a base consultada foi a esperada
3. Compare o valor com o banco ou consulta manual
4. Marque se o retorno veio correto, parcial ou incorreto
5. Se errar, registre se o problema foi de:
   - interpretacao
   - roteamento
   - periodo
   - filtro
   - SQL
   - formatacao

---

## Validacao — V_KARDEX

| # | Pergunta | Base esperada | Intent esperado | O que validar no retorno |
|---|----------|---------------|-----------------|--------------------------|
| 1 | `Qual o total de LD gerado ontem?` | `V_KARDEX` | `ld_total` | Deve retornar total de LD do dia anterior, sem breakdown de inteiro/FP |
| 2 | `Qual foi a geracao de LD nesse mes?` | `V_KARDEX` | `ld_total` | Deve retornar total do mes atual, sem assumir operador |
| 3 | `Quanto de LD o ezequiel.nunes identificou nesse mes?` | `V_KARDEX` | `geracao_ld_por_operador` | Deve filtrar apenas o operador informado |
| 4 | `Quanto de LD o igor.chiva identificou ontem?` | `V_KARDEX` | `geracao_ld_por_operador` | Deve usar operador + periodo diario corretamente |
| 5 | `Quem gerou mais LD em abril de 2026?` | `V_KARDEX` | `ranking_usuarios_ld` | Deve retornar ranking de operadores por LD |
| 6 | `Quais produtos tiveram mais LD em abril de 2026?` | `V_KARDEX` | `ranking_produtos_ld` | Deve retornar ranking de produtos com mais LD |
| 7 | `Producao de ontem por qualidade` | `V_KARDEX` | `resumo_qualidade` | Deve quebrar em Inteiro + LD + FP + Total |
| 8 | `Quanto foi inteiro, LD e fora de padrao ontem?` | `V_KARDEX` | `resumo_qualidade` | Deve exibir todas as categorias de qualidade no mesmo retorno |
| 9 | `Qual foi a producao por qualidade em abril de 2026?` | `V_KARDEX` | `resumo_qualidade` | Deve consolidar o periodo inteiro com breakdown correto |
| 10 | `Quais meses voce tem dados de qualidade?` | `V_KARDEX` | `periodos_disponiveis` | Deve listar cobertura temporal da base de qualidade |

### Resultado esperado da rodada V_KARDEX

- Perguntas de `LD total` nao devem cair em resumo por qualidade
- Perguntas de operador nao devem trazer total geral
- Perguntas de qualidade devem trazer breakdown, nao apenas um numero unico
- O periodo deve mudar corretamente entre `ontem`, `nesse mes` e meses fechados

---

## Validacao — SH6

| # | Pergunta | Base esperada | Intent esperado | O que validar no retorno |
|---|----------|---------------|-----------------|--------------------------|
| 1 | `Qual foi a producao total da fabrica ontem?` | `SH6` | `total_fabrica` | Deve retornar total diario correto |
| 2 | `Qual foi a producao total da fabrica em abril de 2026?` | `SH6` | `total_fabrica` | Deve retornar total mensal correto |
| 3 | `Qual a producao da extrusora?` | `SH6` | `comparativo_extrusoras` | Deve trazer comparativo entre MAC1 e MAC2 |
| 4 | `Qual o valor total de cada MAC em abril de 2026?` | `SH6` | `comparativo_extrusoras` | Deve retornar uma linha por extrusora |
| 5 | `Qual foi a producao da Extrusora 1 em abril de 2026?` | `SH6` | `comparativo_extrusoras` ou filtro por recurso | Deve considerar somente recurso `0003` |
| 6 | `Qual a soma da producao dessas extrusoras em abril de 2026?` | `SH6` | `total_fabrica` | Deve somar o que foi exibido no comparativo |
| 7 | `Qual a producao total dia a dia de 01/04 ate 08/04` | `SH6` | `producao_por_dia` | Deve retornar uma linha por dia e total do periodo |
| 8 | `Quanto o celio.divino produziu em abril de 2026?` | `SH6` | `producao_por_operador` | Deve filtrar apenas o operador informado |
| 9 | `Quem mais produziu em abril de 2026?` | `SH6` | `ranking_producao_geral` | Deve retornar ranking de producao por operador |
| 10 | `Quais meses voce tem dados de producao?` | `SH6` | `periodos_disponiveis` | Deve listar cobertura temporal da base SH6 |

### Resultado esperado da rodada SH6

- Perguntas de producao nao devem cair na `V_KARDEX`
- Perguntas de comparativo devem separar corretamente MAC1 e MAC2
- Perguntas dia a dia nao devem retornar um unico total compactado
- Perguntas por operador devem respeitar o nome informado
- A cobertura temporal deve refletir a base real da SH6

---

## Casos de regressao importantes

Use estes testes para garantir que a IA nao volte a errar comportamentos ja corrigidos.

| Pergunta | Risco conhecido | Comportamento esperado |
|----------|-----------------|------------------------|
| `Qual foi a geracao de LD nesse mes?` | Cair em operador ou resumo por qualidade | Deve retornar `ld_total` |
| `E do dia 01/04 ate 06/04?` | Herdar periodo errado ou resetar contexto | Deve herdar o contexto anterior e trocar apenas o periodo |
| `Qual a producao total dia a dia de 01/04 ate 08/04` | Retornar total unico em vez de diario | Deve listar os dias individualmente |
| `Quais meses voce tem dados?` | Responder texto fixo em vez de cobertura real | Deve listar periodos reais das bases |
| `O que voce consegue responder?` | Falar em terceira pessoa | Deve responder como Ayla, em primeira pessoa |

---

## Registro de execucao

Use este bloco como controle manual durante os testes.

| Data | Pergunta | Base esperada | Resultado | Status | Observacao |
|------|----------|---------------|-----------|--------|------------|
|      |          |               |           |        |            |
|      |          |               |           |        |            |
|      |          |               |           |        |            |
|      |          |               |           |        |            |

---

## Legenda de status

- `OK` = respondeu corretamente
- `PARCIAL` = interpretou certo, mas valor ou formato veio incompleto
- `ERRO` = consultou base errada, retornou valor errado ou interpretou errado
