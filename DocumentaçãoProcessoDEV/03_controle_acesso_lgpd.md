# ViniAI — Controle de Acesso e LGPD

**Versão:** 1.6  
**Última atualização:** Maio/2026  
**Base legal:** Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais (LGPD)

---

## Estrutura Organizacional da Viniplast

```
VINIPLAST
│
├── PRODUÇÃO ──────────────────────────────────────────────┐
│   │                                                       │ Perfil "producao"
│   ├── Extrusora  ┐                                        │ acessa a AYLA —
│   ├── Pesagem    ├──► Ayla  (atende todos os sub-setores) │ ela cobre tudo
│   ├── Qualidade  │                                        │
│   └── Expedição  ┘                                        │
│                                                           ┘
├── PCP (Planejamento e Controle de Produção)
│   └── → Iris  +  consulta Ayla  (PCP precisa ver dados de produção)
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

| Perfil (`user_setor`) | Agente(s) acessível(is) | Observação |
|----------------------|------------------------|------------|
| `admin` | Todos | Acesso irrestrito |
| `gerencia` | Todos | Acesso irrestrito |
| `ti` | Todos | Acesso irrestrito |
| `producao` | **Ayla** | Cobre Extrusora, Pesagem, Qualidade e Expedição |
| `pcp` | **Iris** + **Ayla** | PCP precisa consultar dados de produção |
| `rh` | **Nina** | Somente RH |
| `controladoria` | **Maya** | Somente financeiro/custos |
| `vendas` | **Eva** | Somente vendas |
| Não informado | Sem restrição | Retrocompatibilidade — nenhum controle aplicado |

---

## Regras Fundamentais

1. **Restrição entre departamentos** — nunca dentro do mesmo departamento.
   - Um usuário de `producao` vê todos os sub-setores da Produção via Ayla (Extrusora, Pesagem, Qualidade, Expedição).
   - Um usuário de `rh` não vê dados de Produção, Controladoria ou Vendas.

2. **Conversa sempre liberada** — saudações, dúvidas gerais e apresentação do agente (*"o que você faz?"*) nunca são bloqueados, independentemente do perfil.

3. **Sem setor informado = sem restrição** — para compatibilidade com integrações que ainda não enviam `user_setor`.

4. **Perfil não mapeado = sem restrição** — evita bloquear novos perfis ainda não cadastrados em `permissions.py`.

---

## Como Funciona Tecnicamente

### Payload enviado pelo frontend

```json
{
  "user_id": "joao.silva",
  "session_id": "uuid-da-conversa",
  "message": "Quem produziu mais LD em janeiro?",
  "user_setor": "producao"
}
```

### Fluxo de verificação

```
Mensagem recebida
       │
       ▼
É intent livre? (smalltalk / clarify / tipos_informacao)
       │
     Sim → Libera sempre
       │
      Não
       │
       ▼
user_setor informado?
       │
      Não → Libera (retrocompatível)
       │
      Sim
       │
       ▼
Perfil mapeado em _AGENTES_POR_DEPARTAMENTO?
       │
      Não → Libera (perfil futuro, sem restrição)
       │
      Sim
       │
       ▼
agent_id está no conjunto de agentes permitidos?
       │
    ┌──┴──┐
   Sim    Não
    │      │
  Libera  Bloqueia → retorna MENSAGEM_LGPD
```

### Arquivo de configuração

`ai_service_base/ai_service/app/permissions.py`  
Variável: `_AGENTES_POR_DEPARTAMENTO`

---

## Adicionar Novo Departamento

```python
# em permissions.py → _AGENTES_POR_DEPARTAMENTO
"novo_departamento": {
    "id_agente_1",   # agente principal
    "id_agente_2",   # se precisar acessar outro agente também
},
```

---

## Mensagem de Bloqueio

Texto exibido ao usuário quando o acesso é negado. Baseado na LGPD — Art. 6º, incisos I, III, V e VII.

Personalize em `permissions.py` → variável `MENSAGEM_LGPD` com o texto oficial da política de privacidade da Viniplast.

---

## Sistema de Autenticação de Usuários (Backend Node.js)

### Fluxo de login

```
POST /auth/login
  → valida email + senha (bcrypt)
  → retorna JWT (7 dias) + flag force_password_change
  → se force_password_change = true → frontend redireciona para /change-password
```

### Criação de usuários (painel admin)

O admin cria usuários via painel em `/admin`. Campos disponíveis:
- Nome, email, senha temporária, setor, nível de acesso
- **Exigir troca de senha no primeiro acesso** — se ativado, o usuário é obrigado a redefinir a senha antes de entrar no sistema

```
POST /admin/users  { ..., force_password_change: true }
  → usuário criado com flag ativo
  → no próximo login, frontend bloqueia navegação até troca ser feita
  → POST /auth/change-password → zera flag + emite novo token
```

### Proteções implementadas

| Proteção | Implementação |
|----------|--------------|
| Rate limiting login | 10 tentativas / 15 min (`express-rate-limit`) |
| Rate limiting registro | 10 tentativas / 1 hora |
| Rate limiting forgot-password | 5 tentativas / 15 min |
| Token de reset de senha | SHA-256 gravado no banco — token bruto só no email |
| Validade do token de reset | 10 minutos, uso único |
| JWT | HS256, 7 dias, validado com decode local no frontend |
| httpOnly cookie | `auth_token` setado em cookie `httpOnly; SameSite=Lax; path=/` — inacessível via JavaScript, mitiga XSS |
| Auth híbrida | Middleware lê cookie primeiro, Bearer token como fallback — compatível com ambiente sem HTTPS |
| Troca de senha obrigatória | Flag `force_password_change` no banco + bloqueio no frontend |
| AI Service | `X-API-Key` obrigatório em `/v1/chat/process` (validado via env var `AI_API_KEY`) |

### Requisitos de senha

- Mínimo 8 caracteres
- Ao menos 1 letra maiúscula
- Ao menos 1 letra minúscula
- Ao menos 1 número

Validação aplicada no registro, no reset e na troca obrigatória (`validatePassword()` em `auth.ts`).
