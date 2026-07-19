@echo off
chcp 65001 >nul
title Respaldo manual PERNO TODO
echo ============================================
echo   RESPALDO MANUAL PERNO TODO
echo ============================================
echo.
pushd "%~dp0.."
venv\Scripts\python.exe scripts\respaldo.py --cierre
popd
echo.
pause
