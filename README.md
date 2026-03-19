📄 Documentação de Estruturação: Assistente de Vendas Local (ViniPlast) 

    -- 1. Objetivo do Sistema
    Automatizar o atendimento comercial utilizando uma base de conhecimento interna, garantindo respostas rápidas e precisas sem custos de API externa e com total privacidade dos dados.



-- 2. Fluxo de Funcionamento (Arquitetura RAG)
O sistema opera em um ciclo local de quatro etapas:

    a - Captura: O cliente envia uma dúvida pela interface web (Streamlit).

    b - Recuperação: O sistema consulta a pasta db_store para encontrar o trecho exato no seu .txt.

    c - Processamento: A IA local (Llama 3.2) lê o documento e a pergunta.

    d - Resposta: O bot gera a resposta baseada exclusivamente no seu catálogo.




-- 3. Roadmap de Desenvolvimento (Status Atual)

    Fase 1: Motor de Inteligência: Configuração do Ollama para rodar o modelo llama3.2:1b localmente. (CONCLUÍDO)

    Fase 2: Memória Digital: Criação do script database.py para converter o catálogo em vetores. (CONCLUÍDO)

    Fase 3: Interface de Teste: Implementação do Streamlit para conversação em tempo real via navegador. (CONCLUÍDO)

    Fase 4: Integração Externa: Futura criação de endpoints (FastAPI) para conectar ao WhatsApp via Evolution API/n8n.




-- 4. O "Cérebro" e Lógica (Ambiente Python)

    a - Streamlit: Para a interface visual do chat.

    b - LangChain: O framework que orquestra a conversa entre o usuário, o banco de dados e a IA.

    c - Ollama: O servidor local que sustenta o modelo Llama 3.2 sem depender da nuvem.

    d - Llama 3.2 (1b): O modelo de linguagem escolhido pelo excelente desempenho em máquinas locais.




-- 5. Memória e Conhecimento (RAG Local)
    Diferente do plano inicial, optamos por ferramentas que o Windows aceitou sem bloqueios de segurança:

    a - FAISS (Facebook AI Similarity Search): Banco de vetores ultra-rápido que substituiu o ChromaDB para evitar erros de permissão.

    b - Ollama Embeddings: Utilizado para transformar texto em números, garantindo que o "tradutor" seja o mesmo que o "cérebro".




-- 6. Estrutura de Pastas (Organização)

    /app: Contém database.py (alimentação), engine.py (lógica) e web.py (interface).

    /data: Contém o arquivo base_conhecimento.txt (o coração do seu negócio).

    /db_store: A memória processada pronta para consulta.



