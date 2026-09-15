@echo off
REM ====================================================
REM AI Documentary Animation Factory - one-click launcher
REM ====================================================
REM Opens three windows: FastAPI, Remotion dev server, Next.js
REM Make sure Python 3.11+, Node 20+, and FFmpeg are installed
REM and your .env is in this directory.

setlocal
cd /d "%~dp0"

if not exist .env (
  echo .env file not found. Copying .env.example to .env ...
  copy /Y .env.example .env >nul
  echo Please edit .env and add your API keys, then run start.bat again.
  pause
  exit /b 1
)

echo Starting FastAPI backend on http://localhost:8000 ...
start "videoai-backend" cmd /k "cd orchestrator && .venv\Scripts\activate && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

echo Starting Next.js webapp on http://localhost:3000 ...
start "videoai-webapp" cmd /k "cd webapp && npm run dev"

echo.
echo Both services are starting in separate windows.
echo Open http://localhost:3000 once they're ready.
echo.
echo Press any key to close this window (services will keep running).
pause >nul
endlocal
