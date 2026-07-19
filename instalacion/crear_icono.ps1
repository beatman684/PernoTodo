# Crea el acceso directo "PERNO TODO" en el escritorio:
# ventana de aplicación (sin barra del navegador) con impresión directa
# a la impresora predeterminada (kiosk-printing) y el logo del negocio.
param([Parameter(Mandatory = $true)][string]$Raiz)

$navegadores = @(
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe"
)
$navegador = $navegadores | Where-Object { Test-Path $_ } | Select-Object -First 1

$escritorio = [Environment]::GetFolderPath('Desktop')
$ws = New-Object -ComObject WScript.Shell
$acceso = $ws.CreateShortcut("$escritorio\PERNO TODO.lnk")

if ($navegador) {
    $acceso.TargetPath = $navegador
    $acceso.Arguments = "--app=http://localhost:5000 --kiosk-printing --user-data-dir=`"$Raiz\.navegador`" --no-first-run"
} else {
    # Sin Edge/Chrome: abrir en el navegador predeterminado (sin impresión directa)
    $acceso.TargetPath = "http://localhost:5000"
}
$acceso.WorkingDirectory = $Raiz
$acceso.IconLocation = "$Raiz\static\images\logo.ico"
$acceso.Description = "Sistema PERNO TODO"
$acceso.Save()
Write-Host "    Icono creado ($([System.IO.Path]::GetFileName($navegador)))"
