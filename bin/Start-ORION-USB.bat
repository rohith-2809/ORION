@echo off
:: ORION USB PORTABLE STARTUP SCRIPT
:: Launches ORION entirely statelessly off the USB Pendrive.
:: Avoids polluting the host PC's %USERPROFILE% with HF/NeMo cache.

:: 1. Dynamically resolve USB root path (the dir where this script lives)
set "USB_ROOT=%~dp0"
:: Remove trailing backslash for consistency
if "%USB_ROOT:~-1%"=="\" set "USB_ROOT=%USB_ROOT:~0,-1%"

echo ======================================================
echo [ORION] INITIALIZING PORTABLE PLUG-AND-PLAY MODE...
echo Root Directory Active: %USB_ROOT%
echo ======================================================

:: 2. Set environment variables to isolate cache to the USB
set "HF_HOME=%USB_ROOT%\.cache\huggingface"
set "NEMO_CACHE_DIR=%USB_ROOT%\.cache\nemo"
set "ORION_RAG_DIR=%USB_ROOT%\.cache\orion_rag"
set "TRANSFORMERS_CACHE=%USB_ROOT%\.cache\transformers"

:: Ensure cache directories exist on the USB
if not exist "%HF_HOME%" mkdir "%HF_HOME%"
if not exist "%NEMO_CACHE_DIR%" mkdir "%NEMO_CACHE_DIR%"
if not exist "%ORION_RAG_DIR%" mkdir "%ORION_RAG_DIR%"

:: 3. Inject Portable Python and Node into PATH
:: Assuming they are placed in E:\PortablePython and E:\PortableNode
set "PATH=%USB_ROOT%\PortablePython;%USB_ROOT%\PortablePython\Scripts;%USB_ROOT%\PortableNode;%PATH%"

echo Checking portable binaries...
python --version 2>NUL
if errorlevel 1 (
    echo [ERROR] Portable Python not found at %USB_ROOT%\PortablePython.
    echo Please ensure Python is properly configured for portable execution.
    pause
    exit /b
)

node --version 2>NUL
if errorlevel 1 (
    echo [WARNING] Portable Node.js not found at %USB_ROOT%\PortableNode.
    echo Frontend might fail to launch.
)

:: 4. Start ORION
echo [ORION] Launching Backend Services...
:: We will launch the backend process in a separate visible Command Prompt window
start "ORION Backend (Portable)" /D "%USB_ROOT%\ORION" cmd /k "python server.py"

echo Waiting for API to bind...
timeout /t 5 >nul

echo [ORION] Launching Windows Telemetry Agent...
start "ORION Telemetry Agent" /D "%USB_ROOT%\ORION" cmd /k "python windows_agent.py"

echo [ORION] Launching Frontend Interface...
start "ORION Dashboard" /D "%USB_ROOT%\ORION\orion" cmd /k "npm run dev"

:: 5. Open Browser safely
echo Launching Dashboard in default browser...
timeout /t 3 >nul
start http://localhost:5173

echo ======================================================
echo [ORION] SYSTEM ONLINE (USB MODE)
echo Close the black terminal windows to shutdown safely.
echo ======================================================
pause
