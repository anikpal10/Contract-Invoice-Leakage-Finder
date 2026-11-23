@echo off
set PYTHONPATH=.;.venv\Lib\site-packages
start "Leakage Backend" /B .venv\Scripts\python.exe run_backend.py
start "Leakage Frontend" /B cmd /c "cd frontend && node ./node_modules/vite/bin/vite.js --host 0.0.0.0 --port 5173"

