# ViniAI — Base de Conhecimento

> Vault Obsidian do projeto ViniAI — memória longa de arquitetura, decisões e convenções.
> Mantido junto ao código em `project_memory/`. Ignorado pelo git.

---

## Projeto

- [[Visão-Geral]] — o que é, objetivo, stack
- [[Arquitetura-Geral]] — diagrama de serviços, portas, IPs, fluxo de mensagem

## Agentes de IA

- [[Agentes]] — Ayla (ativo), Iris, Maya, Nina, Eva (futuros)

## Bancos de Dados

- [[SQLServer]] — METABASE, tabelas industriais, regras de query
- [[PostgreSQL]] — N8N, histórico de conversas, autenticação

## Interpretador e RAG

- [[Interpretacao-de-Intencao]] — 19 regras, períodos, extração de entidades
- [[RAG-Conversacional]] — carry-over, period-inherit, auto-inject

## Integrações

- [[Claude-Code]] — estratégia de contexto persistente com Claude Code
- [[Fluxos-n8n]] — automações N8N, integração com o sistema

## Operações

- [[Deploy]] — NSSM, reiniciar serviços, variáveis de ambiente
- [[Pendencias]] — backlog técnico e bugs conhecidos
- [[Changelog]] — log automático de sessões de desenvolvimento

## Decisões Técnicas

- [[Decisoes-Tecnicas]] — por que cada escolha foi feita

---

> **Regra central:**
> Banco = verdade operacional | Obsidian = memória longa do projeto | CLAUDE.md = resumo do agente
