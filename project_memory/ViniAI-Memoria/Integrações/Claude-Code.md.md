# Claude Code — Contexto Persistente

## Estratégia de Memória

O ViniAI usa três camadas de contexto para o Claude Code:

| Camada | O que contém | Quando usar |
|--------|-------------|------------|
| `CLAUDE.md` (raiz do projeto) | Stack, regras de banco, tabelas, regras de query, operadores, pendências | Toda sessão — carregado automaticamente |
| `~/.claude/CLAUDE.md` (global) | Perfil do Pedro, projetos ativos, padrões de trabalho | Toda sessão em qualquer projeto |
| Este vault Obsidian | Arquitetura detalhada, decisões, RAG, intents, deploy | Leitura sob demanda quando precisar de contexto profundo |

---

## O que o Claude deve sempre saber (CLAUDE.md)

- Stack: Python FastAPI + Node.js + React
- **SQL Server (METABASE):** SOMENTE dados industriais
- **PostgreSQL (N8N):** SOMENTE autenticação + conversas
- Tabela principal: `dbo.STG_KARDEX` — LD = `QUALIDADE = 'Y'`
- Parâmetros SQL Server: `?` (pyodbc), não `%s`
- EMISSAO é `date` nativo — sem conversão
- USUARIO tem espaços — sempre `LTRIM(RTRIM())`
- Expedição NUNCA entra em rankings de produção
- `app/config.py` é a fonte da verdade de operadores e setores

---

## Convenções de Desenvolvimento

### Commits
- Sempre ao final de uma sessão de mudanças
- Mensagem descritiva em português
- Formato: `Feat:`, `Fix:`, `Docs:`, `Refactor:`

### Documentação
- Atualizar `DocumentaçãoProcessoDEV/` a cada implementação relevante
- Comparar sempre com o código real — versões e limites numéricos devem bater
- Atualizar este vault com novas decisões, pendências e mudanças de arquitetura

### Código
- Não adicionar features além do pedido
- Não criar helpers para operações únicas
- Não adicionar tratamento de erro para cenários impossíveis
- Respostas diretas e concisas — sem sumário no final

---

## Protocolo de Colaboração com Codex

Quando Claude Code e Codex trabalharem no ViniAI, ambos devem operar com revisão cruzada de contexto.

### Regras obrigatórias
- Nenhum agente deve confiar cegamente na resposta anterior do outro
- Toda regra de negócio deve ser confirmada no código atual antes de virar instrução fixa
- Se houver divergência entre vault, `CLAUDE.md` e código, o código atual é a referência principal até a documentação ser corrigida
- Mudanças em `interpreter.py`, `orchestrator.py` e `sql_service_*` exigem revisão conjunta de intenção, roteamento e query

### Checklist de validação mútua
1. Confirmar qual tabela deve responder a pergunta
2. Confirmar qual intent o interpretador está gerando
3. Confirmar qual handler do orchestrator executa a consulta
4. Confirmar filtros de operador, recurso, origem e período
5. Confirmar se a resposta depende de banco real ou só de validação estática

### Quando um agente corrigir o outro
- Registrar o erro original de forma objetiva
- Atualizar a documentação afetada
- Não propagar hipóteses antigas como se ainda fossem válidas
- Se o problema era de roteamento, revisar também exemplos de pergunta do usuário

---

## Como o vault é mantido automaticamente

### Hook Stop (automático)
O arquivo `scripts/sync_memory.py` é executado automaticamente ao final de cada sessão do Claude Code via hook configurado em `.claude/settings.json`.

O script:
1. Detecta quais arquivos de código foram alterados (`git diff HEAD`)
2. Cria ou atualiza `Temp/sessao_YYYY-MM-DD.md` com os arquivos alterados
3. Adiciona entrada no `RunBooks/Changelog.md.md` se houver mudanças
4. Imprime no terminal quais notas do vault precisam ser revisadas

### Leitura automática (CLAUDE.md)
O `CLAUDE.md` do projeto instrui o Claude a:
- Ler `Hub/Home.md.md` ao iniciar cada sessão
- Atualizar a nota correspondente após cada mudança relevante de código

### Fluxo completo de uma sessão
```
Início da sessão
  └─ Claude lê Hub/Home.md.md → decide quais notas ler

Durante a sessão
  └─ Claude edita código → atualiza nota correspondente no vault

Fim da sessão (hook Stop)
  └─ sync_memory.py detecta mudanças
  └─ Registra em Temp/sessao_YYYY-MM-DD.md
  └─ Adiciona ao RunBooks/Changelog.md.md
  └─ Imprime dica: "Vault para revisar: [[X]]"
```

### Como usar este vault numa sessão manualmente
1. Claude Code carrega `CLAUDE.md` automaticamente
2. Para contexto profundo: *"leia o vault Obsidian sobre X"*
3. Claude lê o arquivo `.md.md` correspondente neste vault
4. Após implementações relevantes, atualizar o arquivo correspondente aqui

---

## Arquivos-chave para o Claude

| Arquivo | Por que ler |
|---------|------------|
| `app/config.py` | Operadores, setores e origens — fonte da verdade |
| `app/interpreter.py` | Regras de intent — antes de qualquer mudança no interpretador |
| `app/orchestrator.py` | Fluxo completo — antes de qualquer mudança no roteamento |
| `app/sql_service.py` | Queries existentes — antes de adicionar novas consultas |
| `app/agents.py` | System prompt e capabilities — antes de alterar personalidade |

---

## Links relacionados

- [[Visão-Geral]] — o que é o projeto
- [[Arquitetura-Geral]] — mapa técnico completo
- [[Decisoes-Tecnicas]] — por que cada escolha foi feita
- [[Pendencias]] — o que ainda precisa ser feito
