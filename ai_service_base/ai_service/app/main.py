"""
main.py — Ponto de entrada da API FastAPI.

Define os endpoints HTTP, configurações de CORS e instancia o orquestrador.

Endpoints disponíveis:
  GET  /health              → verifica se a API está no ar
  POST /v1/chat/process     → processa uma mensagem e retorna a resposta do agente

CORS configurado para aceitar requisições dos domínios do frontend (React).
Para adicionar novos domínios, edite a lista `allow_origins` abaixo.
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.orchestrator import ChatOrchestrator
from app.schemas import ChatProcessRequest, ChatProcessResponse

app = FastAPI(
    title="VINIAI AI Service",
    version="0.1.0",
    description="Base inicial do serviço Python para interpretação e orquestração semântica."
)

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://192.168.1.85:3003,http://viniai.viniplast.local:3003")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "Authorization"],
)

orchestrator = ChatOrchestrator()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/v1/chat/process", response_model=ChatProcessResponse)
def process_chat(payload: ChatProcessRequest) -> ChatProcessResponse:
    return orchestrator.process(payload)
