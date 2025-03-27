@echo off
:: Options Scanner Launcher for Windows
:: Run from the project root directory

:: Activate virtual environment
call .venv\Scripts\activate.bat

:: Launch the scanner application
start python src\main.py --web

:: Open web browser to scanner interface
timeout /t 3 >nul

pause