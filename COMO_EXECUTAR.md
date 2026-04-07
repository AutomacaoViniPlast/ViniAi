# ViniAI — Como executar

## Estrutura do projeto

```
ViniAIpy/
├── ai_service_base/ai_service/   ← ViniAI FastAPI (Python) — porta 8000
├── backend/                      ← Autenticação (Node.js) — porta 4000
└── frontAI/                      ← Frontend (React/Vite) — porta 3001
```

---

## Pré-requisitos

- Python 3.11+ instalado
- Node.js 18+ instalado
- PostgreSQL acessível (banco `METABASE` e banco `N8N`)
- n8n configurado e rodando
- NSSM instalado no servidor (para rodar como serviço)

---

## Variáveis de ambiente

### `backend/.env`
```
DB_HOST=192.168.1.85
DB_PORT=5432
DB_NAME=N8N
DB_USER=postgres
DB_PASSWORD=sua_senha
JWT_SECRET=sua_chave_jwt
PORT=4000
```

### `ai_service_base/ai_service/.env`
```
DB_HOST=192.168.1.85
DB_PORT=5432
DB_NAME=METABASE
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
```

### `frontAI/.env`
```
VITE_API_URL=http://IP_DO_SERVIDOR:4000
VITE_N8N_WEBHOOK_URL=http://192.168.1.85:5678/webhook/SEU_WEBHOOK/chat
VITE_VINIAI_URL=http://IP_DO_SERVIDOR:8000
```

---

## Execução em desenvolvimento

### 1. ViniAI FastAPI
```cmd
cd ai_service_base\ai_service
iniciar.bat
```

### 2. Backend Node.js
```cmd
cd backend
npm install
npm run dev
```

### 3. Frontend
```cmd
cd frontAI
npm install
npm run dev
```

---

## Produção no Windows Server com NSSM

### Instalar NSSM
Baixe em https://nssm.cc/download e coloque o executável em `C:\nssm\nssm.exe`  
Ou via Chocolatey: `choco install nssm`

---

### Serviço 1 — ViniAI FastAPI

Abra o CMD como **Administrador** e rode:

```cmd
nssm install ViniAI-FastAPI
```

Configure na janela que abrir:
- **Path:** `C:\caminho\do\projeto\ai_service_base\ai_service\.venv\Scripts\uvicorn.exe`
- **Startup directory:** `C:\caminho\do\projeto\ai_service_base\ai_service`
- **Arguments:** `app.main:app --host 0.0.0.0 --port 8000`

Ou via linha de comando diretamente:
```cmd
nssm install ViniAI-FastAPI "C:\caminho\do\projeto\ai_service_base\ai_service\.venv\Scripts\uvicorn.exe" "app.main:app --host 0.0.0.0 --port 8000"
nssm set ViniAI-FastAPI AppDirectory "C:\caminho\do\projeto\ai_service_base\ai_service"
nssm set ViniAI-FastAPI DisplayName "ViniAI FastAPI"
nssm set ViniAI-FastAPI Description "Servico de IA de consulta de producao fabril"
nssm set ViniAI-FastAPI Start SERVICE_AUTO_START
nssm start ViniAI-FastAPI
```

---

### Serviço 2 — Backend Node.js

Primeiro gere o build:
```cmd
cd backend
npm install
npm run build
```

Depois crie o serviço:
```cmd
nssm install ViniAI-Backend "C:\Program Files\nodejs\node.exe" "dist\server.js"
nssm set ViniAI-Backend AppDirectory "C:\caminho\do\projeto\backend"
nssm set ViniAI-Backend DisplayName "ViniAI Backend"
nssm set ViniAI-Backend Description "Servico de autenticacao ViniAI"
nssm set ViniAI-Backend Start SERVICE_AUTO_START
nssm start ViniAI-Backend
```

---

### Serviço 3 — Frontend (serve estático)

Primeiro gere o build:
```cmd
cd frontAI
npm install
npm run build
```

Instale o `serve` globalmente:
```cmd
npm install -g serve
```

Crie o serviço:
```cmd
nssm install ViniAI-Frontend "C:\Program Files\nodejs\node.exe" "C:\Users\%USERNAME%\AppData\Roaming\npm\node_modules\serve\build\main.js dist -l 3001"
nssm set ViniAI-Frontend AppDirectory "C:\caminho\do\projeto\frontAI"
nssm set ViniAI-Frontend DisplayName "ViniAI Frontend"
nssm set ViniAI-Frontend Description "Frontend ViniAI"
nssm set ViniAI-Frontend Start SERVICE_AUTO_START
nssm start ViniAI-Frontend
```

---

### Gerenciar serviços

```cmd
nssm start   ViniAI-FastAPI
nssm stop    ViniAI-FastAPI
nssm restart ViniAI-FastAPI
nssm status  ViniAI-FastAPI
nssm remove  ViniAI-FastAPI confirm
```

Substitua `ViniAI-FastAPI` por `ViniAI-Backend` ou `ViniAI-Frontend` conforme necessário.

---

### Verificar se está tudo rodando

```cmd
netstat -ano | findstr "4000\|8000\|3001"
```

Todos os três devem aparecer em estado `LISTENING`.

---

## Portas utilizadas

| Serviço | Porta |
|---------|-------|
| ViniAI FastAPI | 8000 |
| Backend Node.js | 4000 |
| Frontend | 3001 |
| n8n | 5678 |
| PostgreSQL | 5432 |
