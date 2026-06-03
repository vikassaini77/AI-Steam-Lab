@echo off
title NeuroLab AI - Integrated Stack Orchestrator
color 0B
cls

echo =======================================================================
echo         __  __                      _          _        _   ___ 
echo        ^|  \/  ^| ___ _   _ _ __ ___ ^| ^|    __ _^| ^|__    / \ ^|_ _^|
echo        ^| ^|\/^| ^|/ _ \ ^| ^| ^| '__/ _ \^| ^|_  / _` ^| '_ \  / _ \ ^| ^| 
echo        ^| ^|  ^| ^|  __/ ^|_^| ^| ^| ^| (_) ^| ^| _^| (_^| ^| ^|_) ^|/ ___ \^| ^| 
echo        ^|_^|  ^|_^|\___^|\__,_^|_^|  \___/^|____\__,_^|_.__//_/   \_\___^|
echo.
echo           PRODUCTION-READY STEM LABORATORY PLATFORM
echo =======================================================================
echo.
echo Select the mode you would like to run:
echo [1] Production Mode (FastAPI serves built static Frontend on Port 8000)
echo [2] Developer Mode (Open TWO separate terminal windows for Backend and Frontend)
echo [3] Exit Orchestrator
echo.
echo =======================================================================
set /p choice="Enter execution choice [1, 2, or 3]: "

if "%choice%"=="1" (
    cls
    echo =======================================================================
    echo               LAUNCHING NEUROLAB AI: PRODUCTION MODE
    echo =======================================================================
    echo.
    echo [*] Checking and building React assets to ensure latest updates...
    cd frontend
    call npm run build
    cd ..
    echo.
    echo [*] Starting FastAPI production server on http://localhost:8000...
    echo [i] Note: Keep this window open. FastAPI serves BOTH backend APIs and UI!
    echo.
    timeout /t 2 >nul
    start "" http://localhost:8000/
    cd backend
    set PYTHONPATH=.
    python app/main.py
    pause
    exit
)

if "%choice%"=="2" (
    cls
    echo =======================================================================
    echo               LAUNCHING NEUROLAB AI: DEVELOPER MODE (DUAL WINDOWS)
    echo =======================================================================
    echo.
    echo [*] Opening Terminal 1: FastAPI Python Backend Server...
    start "NeuroLab AI - FastAPI Backend API" cmd /k "cd backend && set PYTHONPATH=. && python app/main.py"
    
    echo [*] Opening Terminal 2: Vite React Frontend Dev Server...
    start "NeuroLab AI - Vite React Frontend" cmd /k "cd frontend && npm run dev"
    
    echo [*] Launching your browser and routing to http://localhost:5173/...
    echo.
    timeout /t 3 >nul
    start "" http://localhost:5173/
    echo =======================================================================
    echo [v] Both terminals have been successfully spawned side-by-side!
    echo [i] You can view live OpenCV metrics in Terminal 1, and React updates in Terminal 2.
    echo =======================================================================
    timeout /t 5 >nul
    exit
)

if "%choice%"=="3" (
    echo Exiting orchestrator. Have a wonderful coding session!
    timeout /t 2 >nul
    exit
)

echo Invalid choice. Please run the script again and choose 1, 2, or 3.
pause
