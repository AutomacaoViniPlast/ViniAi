# Guia Visual de Uso da IA ViniAI

> Manual rapido para perguntar certo, reduzir ambiguidades e evitar erro de consulta.

---

## Visao Geral

### O que este guia resolve

Quando a pergunta vem vaga, a IA pode:

- misturar fabrica, operador e extrusora
- responder o recorte errado
- pedir clarificacao
- interpretar a consulta de forma incompleta

### O que voce precisa decorar

```text
metrica + recorte + periodo
```

### Exemplo perfeito

```text
Qual foi a producao total da fabrica em abril de 2026?
```

---

## Formula de Ouro

| Parte | O que significa | Exemplos bons |
|---|---|---|
| `metrica` | O que voce quer medir | `producao total`, `LD`, `KGH`, `ranking`, `producao por turno` |
| `recorte` | De quem ou do que voce quer saber | `da fabrica`, `de cada MAC`, `da Extrusora 1`, `do igor.chiva`, `por qualidade` |
| `periodo` | Quando isso aconteceu | `hoje`, `ontem`, `neste mes`, `em abril de 2026`, `de janeiro a marco de 2026` |

### Modelo pronto

```text
O que eu quero medir + de quem/do que + em qual periodo
```

---

## O Que a IA Entende Melhor

### Consultas com maior confianca

- producao total da fabrica
- producao por extrusora
- producao por operador
- producao por turno
- comparativo entre MAC1 e MAC2
- soma de valores exibidos por extrusora
- LD por operador
- qualidade da producao: Inteiro, LD e Fora de Padrao
- ranking de producao
- KGH por extrusora

---

## Como Perguntar Bem

### 1. Diga a metrica

| Pergunte assim | Evite isso |
|---|---|
| `Qual foi a producao total...` | `Qual foi o valor?` |
| `Quanto de LD...` | `Como ficou isso?` |
| `Qual foi o KGH...` | `E aquele numero?` |
| `Qual foi a producao por turno...` | `Quanto deu?` |

### 2. Diga o recorte

| Recorte claro | Recorte ruim |
|---|---|
| `da fabrica` | `disso` |
| `de cada MAC` | `dela` |
| `da Extrusora 1` | `por maquina` |
| `do igor.chiva` | `do pessoal` |
| `por qualidade` | `daquilo` |

### 3. Diga o periodo

| Periodo bom | Periodo ruim |
|---|---|
| `em abril de 2026` | `ultimamente` |
| `hoje` | `agora` |
| `ontem` | `antes` |
| `nesta semana` | `naquela epoca` |
| `de janeiro a marco de 2026` | `outro dia` |

---

## Perguntas Boas, Prontas Para Uso

### Producao total da fabrica

```text
Qual foi a producao total da fabrica em abril de 2026?
Qual foi a producao total da fabrica hoje?
```

### Producao por extrusora

```text
Qual o valor total de cada MAC em abril de 2026?
Qual foi a producao da Extrusora 1 em abril de 2026?
Qual foi a producao da Extrusora 2 hoje?
```

### Soma do comparativo

```text
Qual a soma da producao dessas extrusoras em abril de 2026?
Qual a soma desses valores em abril de 2026?
```

Use a segunda forma somente se a conversa anterior ja estiver falando das extrusoras.

### Producao por operador

```text
Quanto o igor.chiva produziu em abril de 2026?
Quanto o ezequiel.nunes produziu hoje?
```

### LD e qualidade

```text
Quanto de LD o ezequiel.nunes identificou em abril de 2026?
Qual foi a producao por qualidade em abril de 2026?
Qual foi o total de Inteiro, LD e Fora de Padrao em abril de 2026?
```

### Ranking

```text
Quem mais produziu em abril de 2026?
Top 5 de producao em abril de 2026
Quem mais gerou LD em abril de 2026?
```

### Turno

```text
Qual foi a producao por turno em abril de 2026?
```

### KGH

```text
Qual foi o KGH da MAC1 nesta semana?
Qual foi o KGH da Extrusora 2 ontem?
```

---

## Perguntas Ruins Que Geram Problema

### Evite estas formas

```text
Qual foi o valor?
E a producao?
Me mostra por maquina
Qual a soma disso?
Como foi a fabrica?
Quanto deu?
Me mostra o negocio do Igor
Quero o numero da extrusora
```

### Por que elas sao ruins

- nao deixam clara a metrica
- nao deixam claro o recorte
- nao deixam claro o periodo

---

## Antes e Depois

| Pergunta ruim | Pergunta boa |
|---|---|
| `Qual foi o valor?` | `Qual foi a producao total da fabrica em abril de 2026?` |
| `Me mostra por maquina` | `Qual o valor total de cada MAC em abril de 2026?` |
| `Qual a soma disso?` | `Qual a soma da producao dessas extrusoras em abril de 2026?` |
| `E o Igor?` | `Quanto o igor.chiva produziu em abril de 2026?` |
| `E o LD dele?` | `Quanto de LD o igor.chiva identificou em abril de 2026?` |

---

## Follow-up Sem Confundir a IA

### Follow-up bom

```text
E na Extrusora 2 no mesmo periodo?
Agora me mostra a soma desses valores em abril de 2026.
E o mesmo ranking para marco de 2026?
```

### Follow-up arriscado

```text
E a outra?
E o resto?
Agora soma
E o dele?
```

### Regra pratica

Se for continuar uma conversa, repita pelo menos:

- o objeto da consulta
- o periodo, quando houver risco de ambiguidade

---

## Atalhos Por Perfil

### Gestor

- `Qual foi a producao total da fabrica neste mes?`
- `Qual o valor total de cada MAC neste mes?`
- `Quem mais produziu neste mes?`

### Lider de producao

- `Qual foi a producao da Extrusora 1 hoje?`
- `Qual foi a producao por turno hoje?`
- `Qual foi o KGH da MAC2 hoje?`

### Qualidade

- `Quanto de LD o ezequiel.nunes identificou hoje?`
- `Qual foi a producao por qualidade hoje?`
- `Quem mais gerou LD neste mes?`

---

## Regras de Ouro

### Faca isso

- use nomes claros como `fabrica`, `Extrusora 1`, `MAC2`, `igor.chiva`
- sempre informe o periodo
- diga se quer `fabrica`, `operador`, `extrusora`, `turno` ou `qualidade`
- quando quiser comparar, diga `cada MAC`, `MAC1 vs MAC2` ou `por extrusora`

### Nao faca isso

- nao use `valor`, `isso`, `aquilo`, `negocio`
- nao use `por maquina` sem dizer qual ou se quer as duas
- nao omita o periodo quando ele muda o resultado
- nao use follow-up curto demais se a conversa estiver mudando de assunto

---

## Cola Rapida

### Se bateu duvida, use este modelo

```text
Qual foi [metrica] [recorte] [periodo]?
```

### Exemplos

```text
Qual foi a producao total da fabrica neste mes?
Qual o valor total de cada MAC em abril de 2026?
Quanto o igor.chiva produziu hoje?
Qual foi a producao por turno ontem?
```

---

## Resumo Final

### Pergunta boa

- reduz erro
- reduz retrabalho
- reduz clarificacao
- melhora a consulta

### Pergunta vaga

- aumenta ambiguidade
- aumenta chance de resposta incorreta
- aumenta necessidade de contexto

## Frase final para decorar

```text
Pergunte sempre com: metrica + recorte + periodo
```
