@echo off
setlocal

echo ==============================================================================
echo    DEPTHWIZARD SIH 2026 - WINDOWS LAUNCHER
echo ==============================================================================

if exist venv\Scripts\python.exe (
    set "PY_EXE=venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_EXE=python"
    ) else (
        echo [ERROR] Python not found. Please install Python 3.10+ or set up venv.
        pause
        exit /b 1
    )
)

%PY_EXE% scripts\run_app.py %*

endlocal
