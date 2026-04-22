# Memória do Projeto

## Objetivo

Guardar contexto persistente sobre o ViniAI para acelerar o desenvolvimento com Claude Code e evitar reexplicar arquitetura, convenções e decisões a cada nova sessão.

---

## Mapa do Vault

| Nota | Conteúdo |
|------|----------|
| [[Visão-Geral]] | O que é o projeto, stack, infraestrutura |
| [[Arquitetura-Geral]] | Diagrama de serviços, IPs, fluxo de mensagem, estrutura de arquivos |
| [[Agentes]] | Ayla (ativo) e futuros — escopo, operadores, personalidade |
| [[SQLServer]] | Tabelas METABASE, regras de query, conceitos de negócio |
| [[PostgreSQL]] | Banco N8N, histórico de conversas, pool de conexões |
| [[Interpretacao-de-Intencao]] | 19 regras, períodos, entidades, guard de dados |
| [[RAG-Conversacional]] | Carry-over, period-inherit, auto-inject, âncora temporal |
| [[Fluxos-n8n]] | Integração N8N→FastAPI, payload, pendências |
| [[Deploy]] | NSSM, variáveis de ambiente, diagnóstico de erros |
| [[Pendencias]] | Backlog técnico completo |
| [[Decisoes-Tecnicas]] | Por que cada escolha arquitetural foi feita |
| [[Claude-Code]] | Convenções, estratégia de memória, arquivos-chave |

---

## O que guardar aqui

- Arquitetura e fluxo do sistema
- Integrações entre serviços
- Convenções de implementação
- Decisões técnicas e seus motivos
- Regras de negócio críticas (LD, expedição, produção, revisão)
- Estratégia de RAG e interpretação de intenção
- Organização e regras dos bancos de dados
- Pendências e backlog

## O que não guardar aqui

- Dados em tempo real ou métricas operacionais
- Status atual de máquinas ou produção
- Código-fonte completo (fica no repositório)
- Secrets, senhas ou chaves de API

---

## Regra Central

```
Banco de dados  = verdade operacional
Repositório git = código-fonte e histórico de mudanças
Obsidian        = memória longa do projeto (arquitetura, decisões, convenções)
CLAUDE.md       = resumo persistente para o agente de IA
```

---

## Como manter atualizado

Após cada sessão de desenvolvimento relevante:

1. Se mudou arquitetura → atualizar [[Arquitetura-Geral]]
2. Se mudou o interpretador → atualizar [[Interpretacao-de-Intencao]]
3. Se adicionou/removeu operador → atualizar [[Agentes]] e [[SQLServer]]
4. Se resolveu uma pendência → remover de [[Pendencias]]
5. Se tomou uma decisão técnica → registrar em [[Decisoes-Tecnicas]]