@echo off
echo ========================================================
echo  TerraGuard AI - Backend Service Launcher
echo ========================================================

cd /d "%~dp0backend"

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found in backend\venv!
    echo Please run: python -m venv venv and pip install -r requirements.txt
    pause
    exit /b 1
)

echo Activating Python virtual environment...
call venv\Scripts\activate.bat

echo Verifying database and demonstration seed data...
python -m app.seed

echo Launching TerraGuard AI FastAPI REST API on http://localhost:8001 ...
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
