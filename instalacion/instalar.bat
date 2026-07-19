@echo off
chcp 65001 >nul
title Instalador PERNO TODO

:: ── Auto-elevación a administrador ──────────────────────────────
>nul 2>&1 net session || (
  echo Solicitando permisos de administrador...
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

echo ============================================
echo   INSTALADOR PERNO TODO  (todo en un clic)
echo ============================================
echo.

pushd "%~dp0.."
set "RAIZ=%CD%"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python no esta instalado o no esta en el PATH.
  echo Instala Python 3.11+ desde python.org marcando "Add Python to PATH".
  pause & popd & exit /b 1
)

echo [1/6] Creando entorno virtual...
if not exist "venv\Scripts\python.exe" python -m venv venv

echo [2/6] Instalando dependencias...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

echo [3/6] Configurando archivo .env...
if not exist ".env" (
  venv\Scripts\python.exe -c "import secrets; print('# PERNO TODO - Variables de entorno\nFLASK_DEBUG=false\nSECRET_KEY=' + secrets.token_hex(32) + '\nIVA_PCT=15\nHORA_CORTE=20\n# RUTA_RESPALDOS=C:\Respaldos_PernoTodo\n# RUTA_DRIVE=G:\Mi unidad\Respaldos_PernoTodo')" > .env
  echo    .env creado con clave segura nueva.
) else (
  echo    .env ya existe, se conserva.
)

echo [4/6] Verificando la aplicacion...
venv\Scripts\python.exe -c "import app" || (
  echo [ERROR] La aplicacion no importa correctamente. & pause & popd & exit /b 1
)

echo [5/6] Programando arranque automatico y respaldos...
schtasks /create /f /tn "PERNO TODO - Servidor" /sc onlogon /delay 0000:30 ^
  /tr "wscript.exe \"%RAIZ%\instalacion\iniciar_servidor.vbs\"" >nul
schtasks /create /f /tn "PERNO TODO - Respaldo diario" /sc onlogon /delay 0002:00 ^
  /tr "\"%RAIZ%\venv\Scripts\python.exe\" \"%RAIZ%\scripts\respaldo.py\"" >nul
schtasks /create /f /tn "PERNO TODO - Respaldo semanal" /sc weekly /d FRI /st 18:00 ^
  /tr "\"%RAIZ%\venv\Scripts\python.exe\" \"%RAIZ%\scripts\respaldo.py\"" >nul
netsh advfirewall firewall delete rule name="PERNO TODO puerto 5000" >nul 2>&1
netsh advfirewall firewall add rule name="PERNO TODO puerto 5000" dir=in action=allow protocol=TCP localport=5000 >nul

echo [6/6] Creando el icono PERNO TODO en el escritorio...
powershell -NoProfile -ExecutionPolicy Bypass -File "%RAIZ%\instalacion\crear_icono.ps1" -Raiz "%RAIZ%"

echo.
echo ============================================
echo   INSTALACION COMPLETADA
echo ============================================
echo   - Icono PERNO TODO creado en el escritorio
echo   - El sistema arrancara solo al encender la PC
echo   - Respaldos: diario al encender / semanal viernes 6 PM
echo.
echo   Si traes datos de otra computadora, copia pernotodo.db
echo   a la carpeta database\ ANTES de reiniciar.
echo.
echo   Reinicia la computadora para terminar.
echo.
popd
pause
