# Base de Conhecimento da Viniplast

> Este arquivo é a fonte de verdade para perguntas conceituais sobre o processo fabril.
> A Ayla usa este conteúdo quando o usuário faz perguntas como "o que é LD?",
> "como funciona a revisão?", "qual a diferença entre Inteiro e LD?".
> Para adicionar novos conceitos: basta adicionar uma seção ## abaixo.

---

## Lona de PVC / Bobina

A Viniplast produz lonas de PVC em forma de bobinas — rolos grandes de material plástico.
Cada bobina passa por três etapas principais:
1. **Extrusão** — fabricação do filme plástico na máquina
2. **Revisão** — inspeção metro a metro por operadores de qualidade
3. **Expedição** — liberação e envio ao cliente

---

## Extrusora / Extrusão

É o processo de fabricação das lonas. O PVC granulado é derretido e pressionado
através de uma matriz para formar o filme plástico que enrola na bobina.

A Viniplast tem duas extrusoras:
- **MAC1** — recurso interno código `0003`
- **MAC2** — recurso interno código `0007`

Os operadores de extrusão são responsáveis por produzir o material.
A produção é medida em **KG** (quilogramas de material produzido).

---

## Revisão / Qualidade

Após a extrusão, as bobinas passam pela equipe de revisão.
O revisor inspeciona o material metro a metro e classifica cada bobina:

| Classificação | Código | Descrição |
|--------------|--------|-----------|
| Inteiro      | I      | Material aprovado, sem defeito |
| LD           | Y      | Material com defeito identificado |
| Fora de Padrão | P    | Material fora da especificação técnica |

Revisores atuais: `raul.araujo`, `igor.chiva`, `ezequiel.nunes`, `kaua.chagas`

---

## LD — Laudo de Defeito

LD significa **"Laudo de Defeito"** — é o nome dado ao material que apresentou
algum problema durante a revisão: manchas, furos, variação de espessura, bolhas, etc.

- **Código no sistema:** `Y` na coluna de qualidade
- **Impacto:** material LD é vendido com desconto ou descartado, dependendo do defeito
- **Quem identifica:** operadores de revisão
- **Como consultar:** "Quanto de LD o ezequiel.nunes identificou em abril de 2026?"

A geração de LD é um dos principais indicadores de qualidade da produção.

---

## Inteiro

Material **aprovado na revisão**, sem nenhum defeito identificado.
É o padrão de qualidade desejado — bobina que saiu perfeita da extrusão
e passou pela revisão sem problemas.

- **Código no sistema:** `I`
- **Como consultar:** "Qual foi o total de Inteiro em março de 2026?"

---

## Fora de Padrão (FP)

Material que **não atende às especificações técnicas** mas não é necessariamente defeituoso.
Pode ser diferença de cor, espessura fora da tolerância permitida, largura incorreta, etc.

- **Código no sistema:** `P`
- **Diferença para LD:** FP é um desvio de especificação; LD é um defeito físico visível
- **Como consultar:** "Quanto de Fora de Padrão foi registrado em abril?"

---

## BAG

Tipo especial de produto fabricado na Viniplast — sacola plástica.

- **Código do produto:** `MSP008`
- **Diferença das lonas:** BAG não segue a lógica de qualidade (I/Y/P).
  É identificado pelo código do produto, não pela coluna de qualidade.
- **Medição:** quantidade em KG quando a unidade de medida é KG

---

## Expedição

Setor responsável por **liberar e enviar as bobinas para os clientes**.

- Os dados de expedição aparecem no sistema mas **não entram em rankings de produção**
- São movimentações de saída (SD2), não de fabricação
- Servem para rastrear quanto foi enviado a clientes em um período

---

## Turno

A fábrica opera em **três turnos** de trabalho contínuos:

| Turno | Horário |
|-------|---------|
| 1     | 06h00 – 14h00 |
| 2     | 14h00 – 22h00 |
| 3     | 22h00 – 06h00 |

Cada turno tem operadores de extrusão e revisão.
É possível consultar a produção separada por turno.

---

## KGH — KG por Hora

Indicador de **produtividade da extrusora**: quantos quilos de lona são produzidos
por hora de operação da máquina.

- Quanto maior o KGH, mais eficiente está a máquina naquele período
- Útil para identificar quedas de desempenho ou comparar turnos
- **Como consultar:** "Qual foi o KGH da MAC1 nesta semana?"

---

## Metros por Minuto (m/min)

**Velocidade da extrusora** — quantos metros de lona por minuto saem da máquina.

- É um indicador de eficiência operacional, junto com KGH
- Velocidade alta com KGH alto = máquina operando bem
- **Como consultar:** "Qual foi a velocidade da MAC2 em abril?"

---

## MAC1 e MAC2

Nomes informais das duas extrusoras da Viniplast:

| Nome | Código interno | Recurso |
|------|---------------|---------|
| MAC1 | Extrusora 1   | `0003`  |
| MAC2 | Extrusora 2   | `0007`  |

Você pode perguntar sobre cada uma separadamente ou comparar as duas:
- "Qual a produção da MAC1 em abril?"
- "Qual o valor total de cada MAC em abril de 2026?"

---

## Operadores por Setor

**Extrusão (MAC1 / MAC2):**
`celio.divino`, `aramis.leal`, `valdenrique.silva`, `andreson.reis`,
`ednilson.soares`, `nobrega.valter`, `gilmar.santos`

**Revisão / Qualidade:**
`raul.araujo`, `igor.chiva`, `ezequiel.nunes`, `kaua.chagas`
