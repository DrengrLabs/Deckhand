@echo off
cd /d "%~dp0"
title DOUS Deckhand

rem If the app is already running (port 5000 in use), just open the
rem browser to it instead of starting a second copy.
netstat -ano | findstr "127.0.0.1:5000" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo Already running - opening in your browser...
    start "" http://127.0.0.1:5000/
    exit /b
)

python -m pip install -q --no-index --find-links installers\wheels -r requirements.txt || python -m pip install -q -r requirements.txt
start "" http://127.0.0.1:5000/
python app.py
