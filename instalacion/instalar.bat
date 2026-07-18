@echo off
chcp 65001 >nul
title Instalador PERNO TODO
echo ============================================
echo   INSTALADOR PERNO TODO
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

echo [1/4] Creando entorno virtual...
if not exist "venv\Scripts\python.exe" python -m venv venv

echo [2/4] Instalando dependencias...
venv\Scripts\python.exe -m pip install --quiet --upgrade pip
venv\Scripts\python.exe -m pip install --quiet -r requirements.txt

echo [3/4] Configurando archivo .env...
if not exist ".env" (
  venv\Scripts\python.exe -c "import secrets; print('# PERNO TODO - Variables de entorno\nFLASK_DEBUG=false\nSECRET_KEY=' + secrets.token_hex(32) + '\nIVA_PCT=15\n# RUTA_RESPALDOS=C:\Respaldos_PernoTodo\n# RUTA_DRIVE=G:\Mi unidad\Respaldos_PernoTodo')" > .env
  echo    .env creado con clave segura nueva.
) else (
  echo    .env ya existe, se conserva.
)

echo [4/4] Verificando la aplicacion...
venv\Scripts\python.exe -c "import app; print('    Aplicacion OK -', len(list(app.app.url_map.iter_rules())), 'rutas')" || (
  echo [ERROR] La aplicacion no importa correctamente. & pause & popd & exit /b 1
)

echo.
echo ============================================
echo   INSTALACION COMPLETADA
echo ============================================
echo Siguientes pasos:
echo   1. Si traes datos, copia pernotodo.db del USB a la carpeta database\
echo   2. Clic DERECHO en instalacion\configurar_tareas.bat y "Ejecutar como administrador"
echo   3. Reinicia la computadora
echo.
popd
pause
