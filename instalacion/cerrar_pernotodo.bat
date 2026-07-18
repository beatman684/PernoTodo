@echo off
chcp 65001 >nul
title Cierre PERNO TODO
color 1F
mode con cols=64 lines=18
echo.
echo   ==========================================================
echo      CIERRE DEL SISTEMA PERNO TODO
echo   ==========================================================
echo.
echo   Este proceso imprimira el CIERRE DEL DIA, hara la copia
echo   de seguridad y APAGARA la computadora.
echo.
choice /c SN /t 15 /d S /m "  Continuar? (S=si / N=no) - automatico en 15 seg "
if errorlevel 2 exit /b 0

cls
echo.
echo   Abriendo el Cierre del Dia para imprimir...
start "" "http://localhost:5000/cierre_dia?imprimir=1"
echo.
echo   Imprime el reporte (o cancela la impresion si no lo necesitas).
pause
cls
echo.
echo   ==========================================================
echo      REALIZANDO COPIA DE SEGURIDAD
echo.
echo      *** NO APAGUE EL EQUIPO ***
echo   ==========================================================
echo.
pushd "%~dp0.."
venv\Scripts\python.exe scripts\respaldo.py --cierre
popd
if errorlevel 1 (
  color 4F
  echo.
  echo   [ERROR] El respaldo fallo. NO se apagara el equipo.
  echo   Avise al administrador. Detalle en C:\Respaldos_PernoTodo\respaldo.log
  pause
  exit /b 1
)

color 2F
echo.
echo   ==========================================================
echo      RESPALDO COMPLETADO CORRECTAMENTE
echo      El equipo se apagara en 10 segundos...
echo   ==========================================================
shutdown /s /t 10 /c "PERNO TODO: respaldo completado. Apagando el equipo."
