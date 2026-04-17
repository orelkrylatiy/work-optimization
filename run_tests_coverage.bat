@echo off
setlocal

cd /d "%~dp0"

echo.
echo ================================
echo Running tests with coverage...
echo ================================
echo.

if "%~1"=="" (
    ".venv\Scripts\python.exe" -m pytest tests/ --cov=src/hh_applicant_tool --cov-report=html --cov-report=term-missing
) else (
    ".venv\Scripts\python.exe" -m pytest %* --cov=src/hh_applicant_tool --cov-report=html --cov-report=term-missing
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
echo Tests PASSED - coverage report generated
echo ================================
exit /b 0
