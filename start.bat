@echo off
title PrinterMax M58 Control
echo ==========================================
echo    PrinterMax M58 - Bluetooth Printer
echo ==========================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    where python3 >nul 2>nul
    if %errorlevel% neq 0 (
        echo ERROR: Python not found!
        echo Install Python from https://python.org
        pause
        exit /b 1
    )
    set PYTHON=python3
) else (
    set PYTHON=python
)

echo Checking dependencies...
%PYTHON% -m pip install -r requirements.txt --quiet 2>nul

echo.
echo Starting server on http://localhost:5000
echo Open this URL in your browser.
echo Press Ctrl+C to stop.
echo.
%PYTHON% app.py
pause
