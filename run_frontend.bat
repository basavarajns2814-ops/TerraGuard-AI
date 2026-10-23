@echo off
echo ========================================================
echo  TerraGuard AI - Frontend Geospatial Interface Launcher
echo ========================================================

cd /d "%~dp0frontend"

if not exist "node_modules" (
    echo [INFO] Installing frontend dependencies...
    call npm install
)

echo Starting Vite development server on http://localhost:5173 ...
call npm run dev
