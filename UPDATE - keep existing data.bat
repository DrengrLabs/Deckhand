@echo off
rem For a computer that ALREADY has an earlier copy of the app: brings its
rem hitch setups, crew, signatures, History and timesheets into this new
rem copy, then runs the normal installer (which points the desktop icon and
rem start-up shortcut here). The old copy is left untouched as a backup.
title DOUS Deckhand - Update
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0app\installers\update_keep_data.ps1"
if errorlevel 1 (
    echo.
    echo The update couldn't bring the old data over - nothing was changed.
    pause
    exit /b 1
)
call "%~dp0INSTALL - run once.bat"
