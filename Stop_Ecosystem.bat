@echo off
echo Shutting down AI Ecosystem...
taskkill /f /im python.exe /fi "WINDOWTITLE eq C:\WINDOWS\system32\cmd.exe - .\venv\Scripts\python.exe server.py*"
taskkill /f /im python.exe
echo Ecosystem offline.
timeout /t 3
exit
