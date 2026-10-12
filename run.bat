@echo off
REM Double-click to open the app. The first time it creates the environment and installs what it needs.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Setting up the environment ^(first time only^)...
  py -3 -m venv .venv || python -m venv .venv || goto :nopython
  .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
)
where ffmpeg >nul 2>nul || (echo ffmpeg is missing: winget install ffmpeg & pause & exit /b 1)
REM pythonw = no console window
start "" .venv\Scripts\pythonw.exe app.py
exit /b 0
:nopython
echo Python 3.10 or newer not found: winget install Python.Python.3.12
pause & exit /b 1
:fail
echo Installing the dependencies failed.
pause & exit /b 1
