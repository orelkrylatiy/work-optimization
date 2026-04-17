@echo off
REM Run tests for specific module
REM Запуск тестов для конкретного модуля

setlocal enabledelayedexpansion

if "%1"=="" (
    echo.
    echo Usage: run_tests_module.bat [module_name]
    echo.
    echo Examples:
    echo   run_tests_module.bat utils_string
    echo   run_tests_module.bat api_errors
    echo   run_tests_module.bat storage_models
    echo.
    echo Available modules:
    echo   - utils_config
    echo   - utils_date
    echo   - utils_string
    echo   - utils_json
    echo   - api_client
    echo   - api_errors
    echo   - storage_models
    echo   - operations
    echo   - main
    echo.
    exit /b 1
)

cd /d "%~dp0"

echo.
echo ================================
echo Running tests for: %1
echo ================================
echo.

py -3 -m pytest tests/test_%1.py -v --tb=short

if errorlevel 1 (
    echo.
    echo Module %1 tests FAILED
    exit /b 1
) else (
    echo.
    echo Module %1 tests PASSED
    exit /b 0
)
