@echo off
REM Run all tests with verbose output
REM Все тесты с подробным выводом

setlocal enabledelayedexpansion

echo.
echo ================================
echo Running all tests...
echo ================================
echo.

cd /d "%~dp0"

py -3 -m pytest tests/ -v --tb=short

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
