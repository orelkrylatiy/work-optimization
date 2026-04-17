@echo off
REM Run tests with coverage report
REM Запуск тестов с отчетом о покрытии кода

setlocal enabledelayedexpansion

echo.
echo ================================
echo Running tests with coverage...
echo ================================
echo.

cd /d "%~dp0"

py -3 -m pytest tests/ ^
  --cov=src/hh_applicant_tool ^
  --cov-report=html ^
  --cov-report=term-missing ^
  -v ^
  --tb=short

if errorlevel 1 (
    echo.
    echo ================================
    echo Tests FAILED
    echo ================================
    exit /b 1
) else (
    echo.
    echo ================================
    echo Tests PASSED - Coverage report generated
    echo Opening coverage report...
    echo ================================
    echo.

    REM Open HTML coverage report
    if exist htmlcov\index.html (
        start htmlcov\index.html
    )

    exit /b 0
)
