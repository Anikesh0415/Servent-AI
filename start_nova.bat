@echo off
REM start_nova.bat — launch with Intel Arc GPU acceleration
echo Starting NOVA with Intel Arc GPU...

set OLLAMA_GPU=1
set OLLAMA_NUM_GPU=999
set OLLAMA_MAX_VRAM=8192

start /B ollama serve
timeout /t 3 /nobreak >nul

echo Ollama ready with GPU. Starting NOVA...
python server.py
