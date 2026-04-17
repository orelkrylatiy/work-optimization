@echo off
REM Install test dependencies
REM Установить зависимости для тестирования

setlocal enabledelayedexpansion

echo.
echo ================================
echo Installing test dependencies...
echo ================================
echo.

cd /d "%~dp0"

py -3 -m pip install --upgrade pip setuptools wheel

echo.
echo Installing pytest and related packages...
py -3 -m pip install pytest pytest-cov pytest-mock pytest-xdist

echo.
echo Installing project dependencies...
if exist pyproject.toml (
    echo Using poetry...
    py -3 -m pip install poetry
    py -3 -m poetry install --with dev
) else if exist requirements.txt (
    echo Using requirements.txt...
    py -3 -m pip install -r requirements.txt
) else (
    echo Using setup.py...
    py -3 -m pip install -e .
)

echo.
echo ================================
echo Installation complete!
echo ================================
echo.

REM Verify installation
py -3 -m pytest --version

exit /b 0
