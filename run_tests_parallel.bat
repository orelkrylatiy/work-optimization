@echo off
REM Run tests in parallel
REM Запуск тестов параллельно (требует pytest-xdist)

setlocal enabledelayedexpansion

echo.
echo ================================
echo Running tests in parallel...
echo ================================
echo.

cd /d "%~dp0"

echo Checking for pytest-xdist...
py -3 -c "import xdist" 2>nul

if errorlevel 1 (
    echo.
    echo pytest-xdist is not installed!
    echo Installing...
    py -3 -m pip install pytest-xdist
)

echo.
echo Starting parallel tests...
echo.

py -3 -m pytest tests/ -v -n auto --tb=short

if errorlevel 1 (
    echo.
    echo ================================
    echo Tests FAILED
    echo ================================
    exit /b 1
) else (
    echo.
    echo ================================
    echo All tests PASSED
    echo ================================
    exit /b 0
)
