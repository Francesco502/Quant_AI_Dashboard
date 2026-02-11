@echo off
cd /d "%~dp0"
title Quant-AI-Dashboard Launcher

echo ==================================================
echo       Quant-AI-Dashboard Startup Script
echo ==================================================
echo.

REM --- 1. Virtual Environment Check ---
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Found local .venv, activating...
    call ".venv\Scripts\activate.bat"
) else (
    if exist "..\.venv\Scripts\activate.bat" (
        echo [INFO] Found parent .venv, activating...
        call "..\.venv\Scripts\activate.bat"
    ) else (
        echo [WARN] No virtual environment found. Using system Python.
    )
)
echo.

REM --- 2. Password Check ---
if not "%APP_LOGIN_PASSWORD%"=="" goto LAUNCH
if not "%APP_LOGIN_PASSWORD_HASH%"=="" goto LAUNCH

echo [CONFIG] Login Protection
echo 1. Set Temporary Password
echo 2. Start Without Password (Dev Mode)
echo.
set /p choice=Enter choice [1/2] (Default 2): 

if "%choice%"=="1" goto SET_PASS
goto LAUNCH

:SET_PASS
set /p APP_LOGIN_PASSWORD=Enter Password: 
if "%APP_LOGIN_PASSWORD%"=="" echo [WARN] Password empty, using Dev Mode.
goto LAUNCH

:LAUNCH
echo.
echo --------------------------------------------------
echo Starting Services...
echo --------------------------------------------------
echo.

REM Start API Server in a new window, keep open if error (cmd /k)
echo [1/2] Launching API Server (Port 8685)...
start "Quant API Server" cmd /k "python -m uvicorn api.main:app --host 0.0.0.0 --port 8685 --reload"

REM Start Frontend in a new window, keep open if error
echo [2/2] Launching Next.js Frontend (Port 8686)...
if exist "web" (
    start "Quant Frontend" cmd /k "cd web && npm start"
) else (
    echo [ERROR] 'web' directory not found!
    pause
    exit /b
)

echo.
echo ==================================================
echo Services are starting in background windows.
echo Please wait a moment, then visit:
echo.
echo     http://localhost:8686
echo.
echo ==================================================
echo.
pause
