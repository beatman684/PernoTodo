@echo off
chcp 65001 >nul
title Actualizar PERNO TODO
echo ============================================
echo   ACTUALIZANDO PERNO TODO
echo ============================================
echo.
pushd "%~dp0.."

echo [1/4] Respaldo de seguridad previo...
venv\Scripts\python.exe scripts\respaldo.py

echo [2/4] Descargando la ultima version...
git pull --ff-only
if errorlevel 1 (
  echo [ERROR] No se pudo descargar. Revisa la conexion a internet.
  pause & popd & exit /b 1
)

echo [3/4] Actualizando dependencias...
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

echo [4/4] Reiniciando el servidor...
taskkill /f /im pythonw.exe >nul 2>&1
wscript.exe "%~dp0iniciar_servidor.vbs"

echo.
echo ============================================
echo   ACTUALIZACION COMPLETADA
echo   (las migraciones de datos se aplican solas al arrancar)
echo ============================================
popd
pause
