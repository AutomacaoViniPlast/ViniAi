# ViniAI — Contexto do projeto

## O que é
IA de consulta de produção fabril. Backend FastAPI (Python) + PostgreSQL.

## Stack
- FastAPI rodando em localhost:8000
- PostgreSQL em 192.168.1.85:5432 banco METABASE
- View principal: v_kardex_ld

## Colunas importantes da view
- usuario → operador (ex: ezequiel.nunes, igor.chiva, raul.araujo)
- emissao → data no formato DD/MM/YYYY (text) — usar TO_DATE com TRIM
- produto → código do produto (5ª posição = Y é material LD, futuramente I = Inteiro)
- total → peso em KG (double precision)
- turno → turno de produção
- origem → tipo de movimentação: SD1 (Entrada), SD2 (Saída), SD3 (Movimentação Interna)
           Atenção: muitos registros têm origem NULL — não forçar filtro por origem

## Estrutura do código do produto
Exemplo: TD2AYBR1BOBR100
- TD2 → tipo de material (posições 1-3)
- A   → variante (posição 4)
- Y   → indicador de defeito (posição 5): Y=LD, I=Inteiro (futuro)
- BR1 → código de cor (branco)
- BO  → tipo de tecido/acabamento (blackout)
- BR100 → dimensão/tamanho

## Conceitos de negócio (IMPORTANTE — não confundir)
- Produção   = material que saiu da extrusora. Operadores de produção NÃO incluem expedição.
- Revisão    = inspeção do material após extrusão. Identifica defeito (LD = Y) ou inteiro (I).
               Os números da revisão representam o que foi inspecionado, NÃO produzido.
- Expedição  = liberação de bobinas para clientes. NÃO produzem — apenas movimentam.
               NUNCA entram em rankings de produção (excluídos automaticamente).

## Setores e operadores (arquivo: app/config.py — fonte da verdade)
Produção:  (a definir — operadores da extrusora)
Revisão:   raul.araujo, igor.chiva, ezequiel.nunes
Expedição: john.moraes, rafael.paiva, andre.prado, richard.santos, arilson.aguiar

## Estrutura de arquivos
app/config.py      → setores, operadores e tipos de origem (fonte da verdade)
app/db.py          → conexão PostgreSQL com pool (psycopg-pool), lê .env
app/sql_service.py → queries (suportam filtro opcional por origem e setor)
app/orchestrator.py → lógica principal
app/interpreter.py → interpreta intenção, extrai período/setor/origem
app/schemas.py     → modelos Pydantic
app/main.py        → FastAPI entry point com CORS

## Regra anti circular import
config → sem dependências internas
sql_service → importa só db.py
interpreter → importa config, schemas
orchestrator → importa sql_service, interpreter, schemas, context_manager, config
main → importa orchestrator

## Regras de query
- Sempre usar TRIM(usuario) e TRIM(produto) nas queries
- Filtro por origem é OPCIONAL (muitos registros têm NULL)
- Filtro por setor = filtrar lista de usuários via IN (...)
- LD = SUBSTRING(TRIM(produto), 5, 1) = 'Y'

## Próximos passos pendentes
- Integrar LLM (Claude/OpenAI) substituindo o RuleBasedInterpreter
- Período dinâmico mais robusto (hoje/ontem/semana)
- Comparação entre períodos
- Suporte a material I (Inteiro) quando vier do banco
- Novos setores: RH, Administrativo, Vendas
