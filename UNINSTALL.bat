@echo off
rem Removes the app, its templates and its shortcuts from this computer.
rem Asks for confirmation first; everything goes to the Recycle Bin.
title DOUS Deckhand - Uninstall
set "HELPER=%~dp0app\installers\uninstall_app.py"

rem Find Python the same way the installer does (the "python" command may
rem only be Windows' Microsoft Store placeholder).
set "PY="
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do if exist "%%~D\python.exe" set "PY=%%~D\python.exe"
if not defined PY (
    echo Python wasn't found, so the uninstaller can't run.
    echo Delete the desktop icon, the "DOUS Deckhand (background)" shortcut
    echo ^(Win+R, type shell:startup^), and the DOUS HSE folder by hand.
    pause
    exit /b 1
)

rem Run from outside the folder being removed, and keep the python call on
rem the last line with "exit" so cmd never needs to re-read this file
rem after it's been recycled.
cd /d "%TEMP%"
"%PY%" "%HELPER%" & exit /b
