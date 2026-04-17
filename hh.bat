@echo off
set CONFIG_DIR=C:\Users\Maxim\AppData\Roaming\hh-applicant-tool
set PYTHONUTF8=1

py -3 -m poetry --version >nul 2>&1
if %errorlevel%==0 (
    py -3 -m poetry run python -m hh_applicant_tool %*
) else (
    py -3 -c "import sys; sys.path.insert(0, 'src'); from hh_applicant_tool.main import main; raise SystemExit(main())" %*
)
