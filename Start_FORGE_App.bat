@echo off
cd /d "%~dp0"

:: Enable GPU Acceleration for Ollama
set OLLAMA_GPU=1
set OLLAMA_NUM_GPU=999
set OLLAMA_MAX_VRAM=8192

:: Start Ollama silently in background if not already running
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="1" (
    start /b "" ollama serve >nul 2>&1
)

:: Start FORGE Python Backend Server silently in background
start /b "" ".\venv\Scripts\python.exe" server.py >nul 2>&1

:: Wait 3 seconds for WebSocket server readiness
timeout /t 3 /nobreak >nul

:: Launch FORGE Dashboard as a Native Desktop App Window using Brave
start "" "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --app="file:///%~dp0ui/index.html" --window-size=1280,800
