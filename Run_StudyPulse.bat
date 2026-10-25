
@echo off
title StudyPulse Launcher
cd /d "%~dp0"

echo Starting StudyPulse...

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
) else (
    echo Python virtual environment not found!
    pause
    exit /b 1
)

start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8501"

"%PYTHON_EXE%" -m streamlit run "%~dp0app.py"

pause
