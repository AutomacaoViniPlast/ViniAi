# ViniAI — Controle de Acesso e LGPD

**Versão:** 1.0  
**Última atualização:** Abril/2026  
**Base legal:** Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais (LGPD)

---

## Visão Geral

O sistema implementa controle de acesso baseado em perfil de usuário para garantir
que cada colaborador acesse apenas os dados pertinentes ao seu departamento,
em conformidade com os princípios da LGPD.

---

## Lógica de Restrição

A restrição é feita **entre departamentos (agentes)**, não dentro do mesmo agente.

**Exemplo correto:**
- Um usuário de **Produção** acessa a Ayla e vê todos os dados (revisão, expedição, extrusora)
- Um usuário de **RH** não acessa a Ayla (dados de produção não são do domínio dele)
- Um usuário de **Produção** não acessa a Maya (dados financeiros não são do domínio dele)

**O que NÃO é restringido:**
- Conversa natural (saudações, perguntas gerais) — sempre liberada
- Apresentação do agente ("o que você faz?") — sempre liberada

---

## Perfis e Permissões

| Perfil (`user_setor`) | Agentes Acessíveis |
|----------------------|-------------------|
| `admin` | Todos |
| `gerencia` | Todos |
| `ti` | Todos |
| `producao` | Ayla (Produção) |
| `rh` | Nina (RH) — quando implementado |
| `vendas` | Eva (Vendas) — quando implementado |
| `controladoria` | Maya (Controladoria) — quando implementado |
| `pcp` | Iris (PCP) — quando implementado |
| `pesagem` | Lara (Pesagem) — quando implementado |
| `qualidade` | Luna (Qualidade) — quando implementado |
| `logistica` | Vera (Logística) — quando implementado |
| Não informado | Sem restrição (retrocompatível) |

---

## Como Funciona Tecnicamente

### Payload do Frontend
O frontend deve enviar o campo `user_setor` no payload da requisição:

```json
{
  "user_id": "pedro.gil",
  "session_id": "uuid-da-conversa",
  "message": "Quem produziu mais LD em janeiro?",
  "user_setor": "producao"
}
```

### Verificação no Orchestrator
```
1. Mensagem recebida com user_setor="rh"
2. Interpreter detecta: intent="ranking_usuarios_ld", route="sql"
3. permissions.py verifica: perfil "rh" pode acessar agente "producao"?
   → Não pode (rh só acessa "rh")
4. Retorna mensagem formal de LGPD
5. Query SQL não é executada
```

### Arquivo de Configuração
`ai_service_base/ai_service/app/permissions.py`

---

## Mensagem de Bloqueio LGPD

Quando o acesso é negado, o usuário recebe a seguinte mensagem:

> **Acesso Negado — Proteção de Dados Pessoais (LGPD)**
>
> Esta solicitação envolve informações que não estão dentro do escopo de acesso
> autorizado para o seu perfil de usuário.
>
> De acordo com a Lei Geral de Proteção de Dados Pessoais (Lei nº 13.709/2018 — LGPD)
> e com as políticas internas de segurança da informação da Viniplast, o acesso a dados
> de outros departamentos ou além do nível hierárquico do colaborador requer autorização
> expressa do responsável pelo tratamento de dados (DPO) ou da gestão competente.
>
> **Princípios aplicados:**
> - Finalidade — dados usados para fins específicos e legítimos
> - Necessidade — apenas o estritamente necessário é acessado
> - Acesso mínimo — colaborador acessa apenas dados do seu cargo/departamento
> - Segurança — medidas para proteger dados de acessos não autorizados
>
> *Referência legal: Art. 6º, incisos I, III, V e VII, da Lei nº 13.709/2018 (LGPD).*

---

## Personalizar a Mensagem

Edite a variável `MENSAGEM_LGPD` em `app/permissions.py` para adequar ao
texto oficial da política de privacidade da Viniplast.

---

## Adicionar Novo Perfil

Para liberar um novo perfil de usuário, edite o dicionário `_AGENTES_POR_PERFIL`
em `permissions.py`:

```python
_AGENTES_POR_PERFIL = {
    ...
    "novo_perfil": {"agent_id_1", "agent_id_2"},  # agentes que esse perfil pode acessar
}
```
