@echo off
title Laundry Pro – Server Startup
color 0A

echo.
echo  ╔══════════════════════════════════════════════╗
echo  ║         LAUNDRY PRO - AUTO STARTUP           ║
echo  ║      Flask Server + MySQL + Chrome           ║
echo  ╚══════════════════════════════════════════════╝
echo.

:: ── STEP 1: Check Python ────────────────────────────────
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERROR] Python not found!
    echo  Please install Python 3.8+ from https://python.org
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  Found: %%v
echo.

:: ── STEP 2: Install / Upgrade pip ───────────────────────
echo [2/5] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo  pip is up to date.
echo.

:: ── STEP 3: Install requirements ────────────────────────
echo [3/5] Installing Python packages...
echo  Installing Flask...
python -m pip install flask --quiet
echo  Installing mysql-connector-python...
python -m pip install mysql-connector-python --quiet
echo  All packages installed.
echo.

:: ── STEP 4: Check if port 5000 is free ──────────────────
echo [4/5] Checking port 5000...
netstat -ano | findstr :5000 >nul 2>&1
if %errorlevel% equ 0 (
    echo  [WARNING] Port 5000 is already in use.
    echo  Attempting to free port 5000...
    for /f "tokens=5" %%p in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do (
        taskkill /PID %%p /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    echo  Port 5000 freed.
) else (
    echo  Port 5000 is free.
)
echo.

:: ── STEP 5: Start Flask server ───────────────────────────
echo [5/5] Starting Flask server...
echo.
echo  ┌─────────────────────────────────────────────┐
echo  │  Server  : http://localhost:5000             │
echo  │  Network : http://%COMPUTERNAME%:5000        │
echo  │  Admin   : admin / admin123                  │
echo  │  User    : john  / user123                   │
echo  └─────────────────────────────────────────────┘
echo.
echo  Opening Chrome in 3 seconds...
echo  Press Ctrl+C in this window to stop the server.
echo.

:: Change to script directory (where app.py lives)
cd /d "%~dp0"

:: Open Chrome after 3 second delay (in background)
start "" cmd /c "timeout /t 3 /nobreak >nul && start chrome http://localhost:5000"

:: Start Flask (this keeps the window open)
python app.py

:: If Flask exits, pause so user can see error
echo.
echo  [Server stopped]
pause
