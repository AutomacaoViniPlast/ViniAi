# Pendências Técnicas

> Backlog de implementações pendentes, bugs conhecidos e melhorias planejadas.
> Atualizar conforme itens forem resolvidos ou novos forem descobertos.

---

## Críticas — bloqueia funcionalidade

| Item | Detalhe | Arquivo |
|------|---------|---------|
| `kaua.chagas` ausente no setor `producao` | Está em `OPERADORES_ATIVOS` mas não em `SETORES["producao"]["operadores"]`. Consultas por setor produção não o retornam. | `app/config.py` |
| **Valores incorretos nas queries de LD (KARDEX)** | O código usa `SUM(QUANTIDADE)` para LD, mas para registros de LD a coluna correta pode não ser `QUANTIDADE`. Regra de qual coluna usar para LD ainda não foi confirmada — usuário irá explicar. Suspeita: `QUANTIDADE` com `UM=MT` traz metros, não kg. | `app/sql_service_kardex.py` |

---

## Mapeamento de Tabelas

| Tabela | Status | O que falta |
|--------|--------|------------|
| `dbo.STG_APONT_REV_GERAL` | Identificada, não mapeada | Pedro precisa verificar colunas e regras de negócio diretamente no banco |
| `dbo.STG_PROD_SH6_VPLONAS` | Identificada | Aguardando criação dos agentes de PCP / novos contextos |
| `dbo.STG_PROD_SD3` | Identificada | Aguardando criação dos agentes de PCP / novos contextos |

---

## Integrações

| Item | Detalhe | Impacto |
|------|---------|---------|
| N8N sem campo `setor` no payload | O fluxo N8N não envia `setor` no body/metadata | Controle de acesso LGPD não funciona para usuários via N8N |
| Integração WhatsApp | Não implementada | Canal adicional planejado |

---

## Funcionalidades a Implementar

| Funcionalidade | Complexidade | Contexto |
|---------------|-------------|---------|
| Comparação entre períodos (`comparacao_periodos`) | Média | Intent definido no interpretador mas sem handler no orchestrator nem query no sql_service |
| Persistir intent resolvido por `session_id` no banco | Alta | Carry-over atual re-interpreta a mensagem — persistindo o intent, o resultado seria mais preciso |
| Integrar `STG_PROD_SH6` ao AI Service | Alta | Traz dados de KG/hora, horas trabalhadas e motivo do defeito LD (`MOTIVO_Y`) |
| Integrar `STG_PROD_SD3` ao AI Service | Alta | Movimentações internas e motivos de perda |

---

## Novos Agentes (futuros)

| Agente | ID | Departamento | Dependência |
|--------|----|-------------|------------|
| Iris | `pcp` | PCP | Mapear tabelas de PCP no SQL Server |
| Maya | `controladoria` | Controladoria | Mapear tabelas financeiras |
| Nina | `rh` | RH | Mapear tabelas de RH |
| Eva | `vendas` | Vendas | Mapear tabelas comerciais |

---

## Melhorias de Qualidade

| Melhoria | Benefício |
|----------|----------|
| Feedback loop: registrar intents com `[context-carry]` e `confidence < 0.6` | Identificar padrões de falha recorrentes |
| Validação de operador desconhecido em `_extract_operator` | Hoje aceita qualquer login mesmo não cadastrado |
| Substituição parcial do interpretador por LLM com function calling | Mais flexibilidade para variações de linguagem não previstas nas regras |

---

## Links relacionados

- [[Agentes]] — estado atual dos agentes e futuros
- [[SQLServer]] — tabelas identificadas
- [[Fluxos-n8n]] — pendência de campo setor
- [[Decisoes-Tecnicas]] — contexto das decisões que geraram as pendências
