# ai_service

Base inicial do serviço Python para orquestração semântica da IA.

## Rodar local
```bash
cd ai_service
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Endpoints
- `GET /health`
- `POST /v1/chat/process`

## Exemplo de body
```json
{
  "user_id": "5511999999999",
  "session_id": "teste-001",
  "channel": "whatsapp",
  "message": "Qual a geração total de LD do Ezequiel em janeiro de 2026?"
}
```
