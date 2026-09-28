@echo off
REM ============================================
REM Python Pipeline Runner for n8n (Windows Batch)
REM ============================================
REM This script runs the Python pipeline using the local Python environment.
REM Called by n8n via HTTP trigger or Execute Command node.
REM ============================================

setlocal enabledelayedexpansion

REM Configuration
set PROJECT_DIR=C:\n8n-project\scraper
set PYTHON_EXE=python
set PIPELINE_SCRIPT=run_pipeline.py
set VENV_DIR=%PROJECT_DIR%\.venv

REM Colors for output
set RED=\033[91m
set GREEN=\033[92m
set YELLOW=\033[93m
set BLUE=\033[94m
set RESET=\033[0m

echo [%date% %time%] Starting Python Pipeline Runner
echo [%date% %time%] Project Directory: %PROJECT_DIR%

REM Change to project directory
cd /d "%PROJECT_DIR%"
if errorlevel 1 (
    echo [%date% %time%] ERROR: Cannot change to project directory %PROJECT_DIR%
    exit /b 1
)

REM Check if virtual environment exists, use it if available
if exist "%VENV_DIR%\Scripts\python.exe" (
    echo [%date% %time%] Using virtual environment: %VENV_DIR%
    set PYTHON_EXE=%VENV_DIR%\Scripts\python.exe
) else (
    echo [%date% %time%] Using system Python: %PYTHON_EXE%
)

REM Verify Python executable
"%PYTHON_EXE%" --version
if errorlevel 1 (
    echo [%date% %time%] ERROR: Python not found at %PYTHON_EXE%
    exit /b 1
)

REM Check if pipeline script exists
if not exist "%PIPELINE_SCRIPT%" (
    echo [%date% %time%] ERROR: Pipeline script not found: %PIPELINE_SCRIPT%
    exit /b 1
)

REM Run the pipeline
echo [%date% %time%] Executing: %PYTHON_EXE% %PIPELINE_SCRIPT%
"%PYTHON_EXE%" "%PIPELINE_SCRIPT%"

set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% equ 0 (
    echo [%date% %time%] SUCCESS: Pipeline completed successfully (exit code: %EXIT_CODE%)
) else (
    echo [%date% %time%] FAILURE: Pipeline failed with exit code: %EXIT_CODE%
)

exit /b %EXIT_CODE%