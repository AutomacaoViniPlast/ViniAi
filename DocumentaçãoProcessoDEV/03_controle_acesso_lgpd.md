# ViniAI — Controle de Acesso e LGPD

**Versão:** 1.1  
**Última atualização:** Abril/2026  
**Base legal:** Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais (LGPD)

---

## Estrutura Organizacional da Viniplast

A empresa é dividida em **departamentos**. Cada departamento tem acesso apenas
aos agentes de IA do seu próprio domínio. Nenhum departamento acessa dados de outro.

```
VINIPLAST
│
├── PRODUÇÃO ──────────────────────────────────────────────┐
│   │                                                       │ Usuário com perfil
│   ├── Extrusora  → Ayla  (dados gerais de produção)      │ "producao" acessa
│   ├── Pesagem    → Lara  (pesagem de bobinas)            │ TODOS esses agentes
│   ├── Qualidade  → Luna  (controle de qualidade)         │
│   └── Expedição  → Vera  (logística e expedição)         │
│                                                           ┘
├── PCP (Planejamento e Controle de Produção)
│   └── → Iris  + consulta Ayla (necessita de dados de produção)
│
├── RH (Recursos Humanos)
│   └── → Nina  (somente dados de RH)
│
├── CONTROLADORIA
│   └── → Maya  (somente dados financeiros/custos)
│
├── VENDAS
│   └── → Eva   (somente dados de vendas)
│
└── ADMIN / GERÊNCIA / TI → acesso irrestrito a todos os agentes
```

---

## Tabela de Permissões por Departamento

| Perfil (`user_setor`) | Agentes Acessíveis | Obs. |
|----------------------|-------------------|------|
| `admin` | Todos | Acesso total |
| `gerencia` | Todos | Acesso total |
| `ti` | Todos | Acesso total |
| `producao` | Ayla, Lara, Luna, Vera | Todas as sub-áreas de produção |
| `pcp` | Iris + Ayla | PCP precisa consultar dados de produção |
| `rh` | Nina | Apenas RH |
| `controladoria` | Maya | Apenas financeiro/custos |
| `vendas` | Eva | Apenas vendas |
| Não informado | Sem restrição | Retrocompatibilidade |

---

## Lógica de Restrição

A restrição é **entre departamentos**, nunca dentro do mesmo departamento.

**Correto:**
- Usuário de `producao` vê dados de Extrusora, Pesagem, Qualidade e Expedição (todas sub-áreas da Produção)
- Usuário de `rh` **não** vê dados de produção
- Usuário de `producao` **não** vê dados de RH ou Controladoria

**Sempre liberado (sem restrição):**
- Saudações e conversa casual (`smalltalk`)
- Mensagens não identificadas (`clarify`)
- "O que você faz?" (`tipos_informacao`)

---

## Como Funciona Tecnicamente

### 1. Frontend envia o departamento no payload

```json
{
  "user_id": "joao.silva",
  "session_id": "uuid-da-conversa",
  "message": "Quem produziu mais LD em janeiro?",
  "user_setor": "producao"
}
```

### 2. Orchestrator verifica antes de qualquer query

```
Mensagem recebida | user_setor="rh" | agent_id="producao"
       ↓
permissions.verificar_permissao("rh", "producao", "ranking_usuarios_ld")
       ↓
"rh" só acessa {"rh"} → "producao" não está no conjunto
       ↓
Retorna MENSAGEM_LGPD — query SQL não executada
```

### 3. Arquivo de configuração

`ai_service_base/ai_service/app/permissions.py`

Variável principal: `_AGENTES_POR_DEPARTAMENTO`

---

## Adicionar Novo Departamento

Edite `_AGENTES_POR_DEPARTAMENTO` em `permissions.py`:

```python
"novo_departamento": {
    "agent_id_1",   # agente principal do departamento
    "agent_id_2",   # agente adicional se necessário
},
```

---

## Mensagem de Bloqueio (LGPD)

Texto exibido ao usuário quando o acesso é negado.  
Pode ser personalizado com a política oficial da Viniplast editando
a variável `MENSAGEM_LGPD` em `permissions.py`.

Referência aplicada: **Art. 6º, incisos I, III, V e VII — Lei 13.709/2018**.
