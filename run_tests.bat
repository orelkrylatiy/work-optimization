@echo off
setlocal

cd /d "%~dp0"

echo.
echo ================================
echo Running tests...
echo ================================
echo.

if "%~1"=="" (
    ".venv\Scripts\python.exe" -m pytest tests/
) else (
    ".venv\Scripts\python.exe" -m pytest %*
)

if errorlevel 1 (
    echo.
    echo ================================
    echo Tests FAILED
    echo ================================
    exit /b 1
)

echo.
echo ================================
echo Tests PASSED
echo ================================
exit /b 0
