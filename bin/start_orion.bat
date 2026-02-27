@echo off
:: ORION STARTUP SCRIPT
:: Launches Brain, Body, API, and Frontend

set "ORION_DIR=\\wsl$\Ubuntu\home\rohith\ORION"

:: 1. Windows Agent (Admin Required)
:: Check for permissions
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo Requesting Admin privileges for Orion Agent...
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    pushd "%CD%"
    CD /D "%~dp0"

echo [ORION] SYSTEM INITIALIZING...

:: 2. Launch Brain (API + Orchestrator) - New Window
:: Server.py initializes OrionOrchestrator internally, so this is the only Brain process needed.
start "ORION BRAIN & API" wsl -d Ubuntu -u rohith bash -c "cd ~/ORION/src/main && source ~/ORION/ORION-env/bin/activate && python3 server.py; exec bash"

:: 3. Launch Body (Windows Agent) - New Window

:: 4. Launch Body (Windows Agent) - New Window
start "ORION BODY" cmd /k "cd /d %ORION_DIR%\src\security && python windows_agent.py"

:: 5. Launch Frontend - New Window
start "ORION DASHBOARD" wsl -d Ubuntu -u rohith bash -c "cd ~/ORION/orion_ui && npm run dev; exec bash"

:: 6. Open Browser
echo Waiting for services to spin up...
timeout /t 10
start http://localhost:5173

echo [ORION] ALL SYSTEMS GO.
pause
