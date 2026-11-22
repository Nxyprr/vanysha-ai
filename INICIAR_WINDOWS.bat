@echo off
chcp 65001 >nul
title Vanysha AI
cd /d "%~dp0"
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY ( python --version >nul 2>nul && set "PY=python" )
if not defined PY (
  echo No encuentro Python en este equipo.
  echo Voy a intentar instalarlo automaticamente...
  echo.
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  if errorlevel 1 (
    echo.
    echo No pude instalarlo solo. Se abrira la pagina de descarga.
    echo Instala Python y marca la casilla "Add python.exe to PATH".
    start https://www.python.org/downloads/
  ) else (
    echo.
    echo Python instalado.
  )
  echo.
  echo Cuando termine, CIERRA esta ventana y vuelve a hacer doble clic en INICIAR_WINDOWS.bat
  pause
  exit /b
)
%PY% start.py
echo.
pause
