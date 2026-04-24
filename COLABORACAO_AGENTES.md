# Colaboracao Entre Agentes

## Objetivo

Este arquivo define como Codex e Claude Code devem trabalhar juntos no ViniAI sem propagar erro, contexto antigo ou suposicoes nao validadas.

## Ordem de leitura no inicio de qualquer sessao

1. `CLAUDE.md`
2. `project_memory/ViniAI-Memoria/Hub/Home.md.md`
3. Arquivos do codigo diretamente ligados a tarefa
4. Nota do vault correspondente ao arquivo alterado

## Fonte de verdade

- O codigo atual do workspace sempre vence memoria antiga
- `app/config.py` e a fonte de verdade para operadores, setores e origens
- `interpreter.py` define a intencao
- `orchestrator.py` define o roteamento real
- `sql_service_sh6.py` e `sql_service_kardex.py` definem a consulta real

## Regras obrigatorias de colaboracao

- Nenhum agente deve confiar cegamente na resposta anterior do outro
- Toda regra de negocio deve ser confirmada no codigo antes de virar orientacao fixa
- Se houver divergencia entre codigo, vault e `CLAUDE.md`, o agente deve corrigir a documentacao
- Toda correcao de bug deve identificar se o problema estava em:
  - interpretacao
  - roteamento
  - SQL
  - filtro
  - periodo
  - resposta formatada

## Checklist antes de responder algo sensivel

- A pergunta cai na tabela certa?
- O intent gerado esta correto?
- O handler do orchestrator bate com esse intent?
- Os filtros de operador, recurso, origem e periodo estao certos?
- A resposta foi validada no banco real ou so estaticamente?

## Quando um agente corrigir o outro

- Descrever objetivamente o erro anterior
- Explicar a regra correta
- Informar quais arquivos foram alterados
- Dizer se houve validacao real no banco
- Atualizar vault e `CLAUDE.md` se a correcao mudar regra do projeto

## Handoff de sessao

Ao terminar uma sessao, o agente deve deixar claro:

- o que foi corrigido
- o que ainda esta pendente
- o que foi validado
- o que ainda depende de banco real
- quais arquivos foram alterados

## Casos criticos no ViniAI

Sempre revisar com cuidado extra quando a tarefa envolver:

- diferenca entre `SH6` e `V_KARDEX`
- perguntas de `LD`, `Inteiro`, `Fora de Padrao` e `qualidade`
- perguntas com periodo relativo como `ontem`, `esse mes`, `de 01/04 ate 08/04`
- carry-over de contexto entre perguntas seguidas
- filtros por operador autenticado versus operador explicito

## Regra final

Se houver qualquer duvida entre "acho que e isso" e "confirmei no codigo", vale sempre a segunda opcao.
