"""
ViniAI — Serviço de Inteligência Artificial para Produção Industrial.

Pacote principal da aplicação FastAPI. Estrutura de módulos:

  main.py          → Ponto de entrada da API (endpoints, CORS, startup)
  agents.py        → Registro de agentes: nome, domínio e system prompt de cada IA
  config.py        → Regras de negócio: setores, operadores e tipos de origem
  context_manager  → Leitura do histórico de conversa do banco N8N
  db.py            → Pools de conexão PostgreSQL (METABASE e N8N)
  interpreter.py   → Interpretador de intenções baseado em regras (sem LLM)
  llm_handler.py   → Integração com ChatGPT (OpenAI) para conversação natural
  orchestrator.py  → Orquestrador principal: interpreta → verifica permissão → responde
  permissions.py   → Controle de acesso por setor e mensagem formal de LGPD
  schemas.py       → Modelos Pydantic de entrada e saída da API
  sql_service.py   → Queries SQL executadas contra a view v_kardex_ld
"""
