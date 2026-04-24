# N8N — Automações e Integrações

## Papel do N8N no ViniAI

O N8N (`192.168.1.85:5678`) atua como **camada de automação e integração**. Ele orquestra fluxos que conectam canais externos (WhatsApp, etc.) ao sistema ViniAI e automatiza tarefas recorrentes.

O banco PostgreSQL (`192.168.1.85:5432`, banco `N8N`) é usado pelo N8N como armazenamento interno, mas também é onde o ViniAI guarda o histórico de conversas.

---

## Integração com o AI Service

O N8N pode enviar mensagens diretamente ao FastAPI via `POST /v1/chat/process`.

### Payload esperado pelo FastAPI

```json
{
  "message": "texto da mensagem",
  "session_id": "identificador_da_sessao",
  "user_id": "id_do_usuario",
  "user_name": "Nome Completo",
  "user_setor": "producao",
  "user_cargo": "operador"
}
```

O orchestrator também aceita esses campos via `metadata` (compatibilidade com N8N):

```json
{
  "message": "...",
  "session_id": "...",
  "metadata": {
    "userName": "Nome",
    "setor": "producao",
    "cargo": "operador"
  }
}
```

> [!warning] Pendência
> O N8N ainda não envia o campo `setor` no body. Isso impede que o sistema saiba o departamento do usuário para controle de acesso LGPD.
> **Correção pendente:** configurar o fluxo N8N para incluir `metadata: { "setor": "{{ $json.setor }}" }`.

---

## Salvamento do Histórico

O Backend Node.js é responsável por salvar cada mensagem no PostgreSQL N8N antes e depois de chamar o FastAPI:

```
1. Usuário envia mensagem → Backend salva no PostgreSQL (role: user)
2. Backend chama FastAPI → recebe resposta
3. Backend salva resposta no PostgreSQL (role: assistant)
```

O FastAPI lê esse histórico em somente leitura via `context_manager.py`.

---

## Canais Suportados (planejado)

| Canal | Status |
|-------|--------|
| Interface Web (frontAI) | Ativo |
| WhatsApp (via N8N) | Planejado |

---

## Fluxos N8N Relevantes

> [!note] Documentação pendente
> Os fluxos N8N específicos ainda não foram mapeados neste vault.
> Quando os fluxos forem documentados, detalhar aqui:
> - Nome do fluxo
> - Trigger (webhook, agendado, etc.)
> - Nodes principais
> - Campos passados ao ViniAI

---

## Links relacionados

- [[PostgreSQL]] — banco compartilhado com N8N
- [[Arquitetura-Geral]] — posição do N8N no sistema
- [[Pendencias]] — pendência do campo setor no payload
