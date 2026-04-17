@echo off
REM Test runner menu
REM Главное меню для запуска тестов

setlocal enabledelayedexpansion

:menu
cls
echo.
echo ====================================
echo     TEST RUNNER MENU
echo ====================================
echo.
echo 1. Run all tests
echo 2. Run tests with coverage
echo 3. Run specific module tests
echo 4. Run tests in parallel
echo 5. Install test dependencies
echo 6. Run edge case tests only
echo 7. Stop on first failure
echo 0. Exit
echo.
set /p choice="Select option (0-7): "

if "%choice%"=="1" goto run_all
if "%choice%"=="2" goto run_coverage
if "%choice%"=="3" goto run_module
if "%choice%"=="4" goto run_parallel
if "%choice%"=="5" goto setup
if "%choice%"=="6" goto run_edge_cases
if "%choice%"=="7" goto run_fail_fast
if "%choice%"=="0" goto exit
echo Invalid choice!
timeout /t 2
goto menu

:run_all
cls
echo.
echo Running all tests...
echo.
cd /d "%~dp0"
py -3 -m pytest tests/ -v --tb=short
pause
goto menu

:run_coverage
cls
echo.
echo Running tests with coverage...
echo.
cd /d "%~dp0"
py -3 -m pytest tests/ ^
  --cov=src/hh_applicant_tool ^
  --cov-report=html ^
  --cov-report=term-missing ^
  -v ^
  --tb=short
echo.
echo Opening coverage report...
if exist htmlcov\index.html (
    start htmlcov\index.html
)
pause
goto menu

:run_module
cls
echo.
echo Available modules:
echo.
echo - utils_config
echo - utils_date
echo - utils_string
echo - utils_json
echo - api_client
echo - api_errors
echo - storage_models
echo - operations
echo - main
echo.
set /p module="Enter module name (or 'cancel'): "
if /i "%module%"=="cancel" goto menu
cd /d "%~dp0"
py -3 -m pytest tests/test_%module%.py -v --tb=short
pause
goto menu

:run_parallel
cls
echo.
echo Checking for pytest-xdist...
py -3 -c "import xdist" 2>nul
if errorlevel 1 (
    echo Installing pytest-xdist...
    py -3 -m pip install pytest-xdist
)
echo.
echo Running tests in parallel...
echo.
cd /d "%~dp0"
py -3 -m pytest tests/ -v -n auto --tb=short
pause
goto menu

:setup
cls
echo.
echo Installing test dependencies...
echo.
cd /d "%~dp0"
py -3 -m pip install --upgrade pip pytest pytest-cov pytest-mock pytest-xdist
if exist pyproject.toml (
    echo Installing via poetry...
    py -3 -m pip install poetry
    py -3 -m poetry install --with dev
)
echo.
echo Installation complete!
pause
goto menu

:run_edge_cases
cls
echo.
echo Running edge case tests...
echo.
cd /d "%~dp0"
py -3 -m pytest tests/ -k edge_cases -v --tb=short
pause
goto menu

:run_fail_fast
cls
echo.
echo Running tests - stopping on first failure...
echo.
cd /d "%~dp0"
py -3 -m pytest tests/ -v -x --tb=short
pause
goto menu

:exit
exit /b 0
