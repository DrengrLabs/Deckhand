@echo off
rem One-time setup on a new computer. Double-click this once.
rem   1. Installs Python if needed (bundled, silent, no admin needed)
rem   2. Installs the Python packages the app needs (bundled, no internet)
rem   3. Installs Topaz SigWeb (signature pad support) if it isn't already
rem   4. Puts a "DOUS Deckhand" icon on the desktop
rem   5. Makes the app start silently whenever this computer starts, so a
rem      Chrome bookmark to http://127.0.0.1:5000/ always works
rem   6. Opens the app
title DOUS Deckhand - Install
set "HERE=%~dp0"
set "APPDIR=%~dp0app\"

cd /d "%APPDIR%" || goto :fail_location

rem Files copied from email / Teams / OneDrive / a download carry a
rem "blocked" mark that can stop Windows running them. Clear it.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%HERE%' -Recurse -File | Unblock-File" >nul 2>nul

rem Copying/unzipping drops the templates' read-only protection; put it back.
attrib +r "%HERE%templates\*.pdf" /s >nul 2>nul

rem PC Matic SuperShield blocks unknown programs (the Python installer,
rem SigWeb, the app itself). Programs can't change its settings, so if PC
rem Matic is on this computer, walk the person through doing it.
call :pcmatic_check
if defined PCMATIC (
    echo.
    echo  ===============================================================
    echo   PC MATIC IS ON THIS COMPUTER - one quick setting first:
    echo  ===============================================================
    echo    1. Click the ^^ arrow next to the clock ^(bottom-right^).
    echo    2. Click the green SuperShield icon.
    echo    3. Choose: Protection Level ^> Block Notification Method ^>
    echo       Prompt for Override.
    echo.
    echo   From now on, whenever PC Matic pops up during this install,
    echo   click ALWAYS ALLOW ^(not just Allow^).
    echo  ===============================================================
    echo.
    echo   Press any key once that's done...
    pause >nul
)

rem ---- Python: use a suitable one if present, otherwise install the
rem copy bundled in app\installers (per-user, silent, no admin needed).
rem Note: Windows has a fake "python" that only opens the Microsoft Store,
rem so Python is tested by actually running it, not just finding it.
set "PY="
call :find_python
if not defined PY call :install_python
if not defined PY goto :no_python
for /f "usebackq delims=" %%V in (`call "%PY%" --version 2^>^&1`) do set "PYVER=%%V"
echo Using %PYVER%

rem The packages are bundled in app\installers\wheels, so no internet is
rem needed. Only if that fails (e.g. a Python version newer than the
rem bundle) does it try downloading them instead.
echo Installing required packages (this can take a minute)...
"%PY%" -m pip install --disable-pip-version-check --no-index --find-links "installers\wheels" -r requirements.txt > "%TEMP%\dous_pip_install.log" 2>&1
if errorlevel 1 (
    echo  Bundled packages didn't fit this computer - trying the internet instead...
    "%PY%" -m pip install --disable-pip-version-check -r requirements.txt >> "%TEMP%\dous_pip_install.log" 2>&1
)
if errorlevel 1 (
    copy /y "%TEMP%\dous_pip_install.log" "%HERE%install_error_log.txt" >nul
    echo.
    echo  ===============================================================
    echo   The package install FAILED. Here is what Python reported:
    echo  ===============================================================
    type "%TEMP%\dous_pip_install.log"
    echo  ===============================================================
    echo   A copy was saved to: DOUS Deckhand\install_error_log.txt
    echo   Send a photo of this window ^(or that file^) for help.
    call :relocate_tip
    pause
    exit /b 1
)

rem Topaz signature pad support (SigWeb). setup_sigweb.ps1 installs SigWeb
rem if needed and sets the pad model to the T-LBK460 automatically. It runs
rem only if SigWeb is missing or set to a different pad, and needs one
rem Windows permission (admin) prompt.
set "NEED_SIGWEB="
sc query SigREST >nul 2>nul || set "NEED_SIGWEB=1"
findstr /i /c:"TabletModel=SigLiteLCD1X5" "%WINDIR%\SigPlus.ini" >nul 2>nul || set "NEED_SIGWEB=1"
if not defined NEED_SIGWEB (
    echo Topaz SigWeb is already installed and set up for the pad.
    goto :sigweb_done
)
if not exist "installers\sigweb.exe" (
    echo Topaz SigWeb installer not found in app\installers - skipping.
    echo Signatures can still be drawn with the mouse / touchscreen.
    goto :sigweb_done
)
echo.
echo Setting up Topaz SigWeb for the signature pad...
echo  - Windows will ask for permission ^(admin^) - click Yes.
echo  - If the Topaz installer opens, click through it accepting the
echo    defaults. The pad model is set automatically afterwards.
echo.
set "SIGPS=%APPDIR%installers\setup_sigweb.ps1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Start-Process powershell -Verb RunAs -Wait -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File \"' + $env:SIGPS + '\"') } catch { exit 1 }"
if errorlevel 1 (
    echo  SigWeb setup was skipped ^(permission not given^). The app still works;
    echo  run this INSTALL file again later to set up the Topaz pad.
)
:sigweb_done

for /f "usebackq delims=" %%P in (`call "%PY%" -c "import sys,os;print(os.path.join(os.path.dirname(sys.executable),'pythonw.exe'))"`) do set "PYW=%%P"

echo Creating shortcuts...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$app = (Get-Location).Path; $pyw = $env:PYW; $sh = New-Object -ComObject WScript.Shell;" ^
  "foreach ($f in @(([Environment]::GetFolderPath('Desktop') + '\DOUS TRA-TBT App.lnk'), ([Environment]::GetFolderPath('Startup') + '\DOUS TRA-TBT App (background).lnk'))) { Remove-Item -LiteralPath $f -ErrorAction SilentlyContinue };" ^
  "$d = $sh.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\DOUS Deckhand.lnk');" ^
  "$d.TargetPath = $pyw; $d.Arguments = '\"' + $app + '\start_app.pyw\"'; $d.WorkingDirectory = $app;" ^
  "$d.IconLocation = $app + '\static\favicon.ico,0'; $d.Description = 'Open the DOUS Daily TRA / TBT app'; $d.Save();" ^
  "$s = $sh.CreateShortcut([Environment]::GetFolderPath('Startup') + '\DOUS Deckhand (background).lnk');" ^
  "$s.TargetPath = $pyw; $s.Arguments = '\"' + $app + '\start_app.pyw\" --background'; $s.WorkingDirectory = $app;" ^
  "$s.IconLocation = $app + '\static\favicon.ico,0'; $s.Description = 'Keeps the DOUS TRA / TBT app running'; $s.Save()"
if errorlevel 1 (
    echo Could not create the shortcuts.
    call :relocate_tip
    pause
    exit /b 1
)

echo Starting the app...
start "" "%PYW%" "%APPDIR%start_app.pyw"

echo.
echo Done. Use the "DOUS Deckhand" icon on the desktop from now on,
echo or bookmark http://127.0.0.1:5000/ in Chrome - it will keep working
echo after the computer restarts.
echo.
echo Leave the "DOUS Deckhand" folder where it is - the app runs from there.
echo.
if defined PCMATIC (
    echo  ===============================================================
    echo   LAST STEP FOR PC MATIC:
    echo  ===============================================================
    echo    1. In the app that just opened, capture a signature and
    echo       generate one PDF - click ALWAYS ALLOW on any PC Matic pop-up.
    echo    2. Then set SuperShield back: green SuperShield icon ^>
    echo       Protection Level ^> Block Notification Method ^> Display Only.
    echo  ===============================================================
    echo.
)
pause
exit /b 0

rem ---------------------------------------------------------------------
:relocate_tip
echo.
echo  ===============================================================
echo   TIP: if this keeps failing, move the whole "DOUS Deckhand" folder
echo   onto the C: drive ^(File Explorer ^> This PC ^> Windows ^(C:^)^)
echo   so it is C:\DOUS Deckhand, then double-click INSTALL again from there.
echo   ^(If it came as a .zip, right-click it ^> Extract All... first.^)
echo  ===============================================================
echo.
exit /b 0

:pcmatic_check
rem Sets PCMATIC=1 if PC Matic is installed: its processes/services
rem (PC Matic, or PC Pitstop - its former name) or its program folder.
set "PCMATIC="
powershell -NoProfile -ExecutionPolicy Bypass -Command "if ((Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'pcmatic|pcpitstop|supershield' }) -or (Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'PC Matic|PC Pitstop|SuperShield' }) -or (Get-ChildItem 'C:\Program Files*\PC Matic*','C:\Program Files*\PC Pitstop*' -Directory -ErrorAction SilentlyContinue)) { exit 0 } else { exit 1 }" >nul 2>nul && set "PCMATIC=1"
exit /b 0

:fail_location
echo.
echo The installer couldn't open its own app folder:
echo     %APPDIR%
call :relocate_tip
pause
exit /b 1

:find_python
rem A working 64-bit Python 3.10+ on PATH, else the newest per-user or
rem all-users install. (Later matches overwrite earlier ones.)
set "PYCHECK=import sys; sys.exit(0 if sys.version_info >= (3, 10) and sys.maxsize > 2**32 else 1)"
python -c "%PYCHECK%" >nul 2>nul && set "PY=python"
if defined PY exit /b 0
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*") do (
    if exist "%%~D\python.exe" "%%~D\python.exe" -c "%PYCHECK%" >nul 2>nul && set "PY=%%~D\python.exe"
)
exit /b 0

:install_python
set "PYINST="
for %%I in ("%APPDIR%installers\python-3*-amd64.exe") do set "PYINST=%%~fI"
if not defined PYINST exit /b 0
echo.
echo Python isn't installed on this computer - installing it now.
echo This takes a minute or two; no windows will open...
"%PYINST%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=0 Include_test=0 Include_doc=0 Shortcuts=0 AssociateFiles=0
call :find_python
if defined PY echo Python installed.
exit /b 0

:no_python
echo.
echo  ===============================================================
echo   Python could not be installed automatically.
echo  ===============================================================
echo   - If PC Matic SuperShield is on, pause it and run this again.
echo   - Or install Python from python.org ^(tick "Add python.exe to
echo     PATH"^), then double-click this file again.
call :relocate_tip
pause
exit /b 1
