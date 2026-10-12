@echo off
REM Doble clic para abrir la app. La primera vez crea el entorno e instala lo necesario.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Preparando entorno ^(solo la primera vez^)...
  py -3 -m venv .venv || python -m venv .venv || goto :nopython
  .venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
)
where ffmpeg >nul 2>nul || (echo Falta ffmpeg: winget install ffmpeg & pause & exit /b 1)
REM pythonw = sin ventana de consola
start "" .venv\Scripts\pythonw.exe app.py
exit /b 0
:nopython
echo No encuentro Python 3.10 o superior: winget install Python.Python.3.12
pause & exit /b 1
:fail
echo Ha fallado la instalacion de dependencias.
pause & exit /b 1
