@echo off
chcp 65001 >nul
title Configurar tareas PERNO TODO
echo ============================================
echo   CONFIGURAR ARRANQUE, RESPALDOS Y ACCESOS
echo ============================================
echo.

net session >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Debes ejecutar este archivo con CLIC DERECHO,
  echo "Ejecutar como administrador".
  pause & exit /b 1
)

pushd "%~dp0.."
set "RAIZ=%CD%"
popd

echo [1/5] Servidor al iniciar sesion...
schtasks /create /f /tn "PERNO TODO - Servidor" /sc onlogon /delay 0000:30 ^
  /tr "wscript.exe \"%RAIZ%\instalacion\iniciar_servidor.vbs\""

echo [2/5] Respaldo diario al encender...
schtasks /create /f /tn "PERNO TODO - Respaldo diario" /sc onlogon /delay 0002:00 ^
  /tr "\"%RAIZ%\venv\Scripts\python.exe\" \"%RAIZ%\scripts\respaldo.py\""

echo [3/5] Respaldo semanal (viernes 6:00 PM)...
schtasks /create /f /tn "PERNO TODO - Respaldo semanal" /sc weekly /d FRI /st 18:00 ^
  /tr "\"%RAIZ%\venv\Scripts\python.exe\" \"%RAIZ%\scripts\respaldo.py\""

echo [4/5] Permitir acceso desde la red local (celular/otras PCs)...
netsh advfirewall firewall delete rule name="PERNO TODO puerto 5000" >nul 2>&1
netsh advfirewall firewall add rule name="PERNO TODO puerto 5000" dir=in action=allow protocol=TCP localport=5000 >nul

echo [5/5] Creando accesos directos en el escritorio...
powershell -NoProfile -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$u=New-Item -Force -Path ($d+'\PERNO TODO.url') -Value \"[InternetShortcut]`nURL=http://localhost:5000`nIconIndex=13`nIconFile=C:\Windows\System32\shell32.dll\";" ^
  "$ws=New-Object -ComObject WScript.Shell;" ^
  "$s=$ws.CreateShortcut($d+'\Cerrar PERNO TODO.lnk'); $s.TargetPath='%RAIZ%\instalacion\cerrar_pernotodo.bat'; $s.WorkingDirectory='%RAIZ%'; $s.IconLocation='C:\Windows\System32\shell32.dll,27'; $s.Save();" ^
  "$a=$ws.CreateShortcut($d+'\Actualizar PERNO TODO.lnk'); $a.TargetPath='%RAIZ%\instalacion\actualizar.bat'; $a.WorkingDirectory='%RAIZ%'; $a.IconLocation='C:\Windows\System32\shell32.dll,238'; $a.Save()"

echo.
echo ============================================
echo   TODO CONFIGURADO
echo ============================================
echo   - El sistema arrancara solo al encender la PC
echo   - Respaldo diario al encender / semanal viernes 6 PM
echo   - Accesos directos creados en el escritorio
echo.
echo   Reinicia la computadora para probar todo.
echo.
pause
