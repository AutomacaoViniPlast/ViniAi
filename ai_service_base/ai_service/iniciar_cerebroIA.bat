@echo off                                                                                                                     
cd /d "C:\Users\pedro.martins\Documents\ViniAi\ai_service_base\ai_service"                                                    
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000