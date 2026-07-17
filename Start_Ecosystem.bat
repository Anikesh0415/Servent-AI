@echo off
echo Booting AI Core...
:: Start Ollama (Will open a minimized window, keeps it open so it doesn't instantly die)
start /min "Ollama Server" cmd /k "ollama serve"

echo Waiting for Ollama to initialize...
timeout /t 5 /nobreak > NUL

:: Start the Python server in a minimized background window
start /min "AIF Backend" cmd /k ".\venv\Scripts\python.exe server.py"

echo Waiting for Backend...
timeout /t 3 /nobreak > NUL

:: Automatically launch the web dashboard
start ui\index.html
exit
