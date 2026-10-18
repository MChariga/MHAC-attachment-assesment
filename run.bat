@echo off
cd /d "%~dp0"
python pipeline\kobo_pipeline.py
if errorlevel 1 exit /b 1
echo Dashboard: http://localhost:8000  (Ctrl+C to stop)
python -m http.server 8000 --directory dashboard
