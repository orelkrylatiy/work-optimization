@echo off
set CONFIG_DIR=C:\Users\Maxim\AppData\Roaming\hh-applicant-tool
C:\Users\Maxim\AppData\Local\Programs\Python\Python314\python.exe -m uvicorn admin.app:app --reload --host 127.0.0.1 --port 8000
