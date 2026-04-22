# Visão Geral — ViniAI

## O que é

Plataforma de inteligência artificial industrial da **Viniplast**. Usuários da fábrica fazem perguntas em linguagem natural e a IA retorna dados reais do banco de produção.

Cada departamento tem um agente com nome, personalidade e domínio de dados próprio. Hoje apenas a **Ayla** (Produção) está ativa.

---

## Problema que resolve

Gestores e operadores precisavam acessar o Metabase ou pedir relatórios ao TI para ver dados simples como *"quem gerou mais LD essa semana?"*. O ViniAI coloca esses dados em linguagem natural, diretamente no chat.

---

## Stack

| Camada | Tecnologia | Porta |
|--------|-----------|-------|
| Frontend | React + Vite | 3003 |
| Backend | Node.js + Express + TypeScript | 4000 |
| AI Service | Python + FastAPI | 8000 |
| Dados industriais | SQL Server METABASE | 50172 |
| Histórico / Auth | PostgreSQL N8N | 5432 |

---

## Regra central dos bancos

> [!warning] Separação obrigatória
> **SQL Server (METABASE):** SOMENTE dados industriais — produção, kardex, revisão, expedição
> **PostgreSQL (N8N):** SOMENTE autenticação de usuário, conversas e mensagens
> Nunca misturar. Nunca gravar dados industriais no PostgreSQL.

---

## Infraestrutura

- **Servidor de produção:** Windows Server em 192.168.1.84 / 192.168.1.111
- **Serviços:** gerenciados pelo NSSM (`C:\metabase\nssm.exe`)
- **Usuário Windows:** `pedro.martins`
- **Projeto no servidor:** `C:\Users\pedro.martins\Documents\ViniAi`
- **Logs:** `C:\Users\pedro.martins\Documents\ViniAi\logs\`
- **Deploy:** push no git → `nssm restart ViniAI-FastAPI`

---

## Links rápidos

- [[Arquitetura-Geral]] — diagrama detalhado e fluxo de mensagem
- [[Agentes]] — estado atual dos agentes
- [[SQLServer]] — tabelas e regras de query
- [[Deploy]] — como fazer deploy e reiniciar serviços
