@echo off
cd /d "%~dp0"
py -3 server.py --open-browser
if errorlevel 1 (
  echo Revisa que Python 3.12 o superior este instalado y que el puerto 8000 este disponible.
  pause
)
