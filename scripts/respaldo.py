"""
Respaldo automático de la base de datos PERNO TODO.

Esquema aprobado:
  - Diario:   una copia por día en disco; se conservan los últimos 7.
  - Semanal:  los viernes desde las 17:00 (o al siguiente encendido si la PC
              estaba apagada); se conservan 8 en disco. Se copia además a la
              carpeta de Google Drive, donde se conservan 90 días.
  - Anual:    el 31 de diciembre (o en enero si falta el del año anterior);
              permanente, en disco y en Drive.

Es idempotente: puede ejecutarse cuantas veces se quiera sin duplicar nada.
Uso:  python scripts/respaldo.py [--cierre]
      --cierre  fuerza el respaldo del día (usado por "Cerrar PERNO TODO")

Rutas configurables en .env:
  RUTA_RESPALDOS  (por defecto C:\\Respaldos_PernoTodo)
  RUTA_DRIVE      (por defecto se detecta la carpeta de Google Drive)
"""
import os
import re
import shutil
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BD = RAIZ / 'database' / 'pernotodo.db'

PATRON_DIARIO = re.compile(r'^pernotodo_(\d{4}-\d{2}-\d{2})\.db$')
PATRON_SEMANAL = re.compile(r'^pernotodo_semana_(\d{4}-\d{2}-\d{2})\.db$')


def _leer_env():
    env = {}
    f = RAIZ / '.env'
    if f.exists():
        for linea in f.read_text(encoding='utf-8', errors='ignore').splitlines():
            linea = linea.strip()
            if linea and not linea.startswith('#') and '=' in linea:
                k, v = linea.split('=', 1)
                env[k.strip()] = v.strip()
    # Las variables de entorno del sistema tienen prioridad sobre el .env
    for clave in ('RUTA_RESPALDOS', 'RUTA_DRIVE'):
        if os.environ.get(clave):
            env[clave] = os.environ[clave]
    return env


ENV = _leer_env()
DIR_RESPALDOS = Path(ENV.get('RUTA_RESPALDOS') or r'C:\Respaldos_PernoTodo')


def _dir_drive():
    """Carpeta de respaldos dentro de Google Drive (si está instalado)."""
    if ENV.get('RUTA_DRIVE'):
        return Path(ENV['RUTA_DRIVE'])
    candidatos = [Path(r'G:\Mi unidad'), Path(r'G:\My Drive'),
                  Path.home() / 'Google Drive', Path.home() / 'Mi unidad']
    for c in candidatos:
        if c.exists():
            return c / 'Respaldos_PernoTodo'
    return None


def log(msg):
    linea = f'[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}'
    print(linea)
    try:
        with open(DIR_RESPALDOS / 'respaldo.log', 'a', encoding='utf-8') as f:
            f.write(linea + '\n')
    except OSError:
        pass


def respaldar(destino):
    """Copia consistente de la BD aunque el servidor esté en uso (API backup de SQLite)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    origen = sqlite3.connect(str(BD))
    copia = sqlite3.connect(str(destino))
    with copia:
        origen.backup(copia)
    copia.close()
    origen.close()
    log(f'Respaldo creado: {destino}')


def _fechas_existentes(carpeta, patron):
    """{fecha: archivo} de los respaldos que siguen el patrón (ignora otros archivos)."""
    resultado = {}
    if carpeta.exists():
        for f in carpeta.iterdir():
            m = patron.match(f.name)
            if m:
                try:
                    resultado[date.fromisoformat(m.group(1))] = f
                except ValueError:
                    pass
    return resultado


def _conservar_ultimos(carpeta, patron, cantidad):
    archivos = _fechas_existentes(carpeta, patron)
    for fecha in sorted(archivos)[:-cantidad]:
        archivos[fecha].unlink()
        log(f'Depurado (rotación): {archivos[fecha].name}')


def _depurar_por_dias(carpeta, patron, dias):
    hoy = date.today()
    for fecha, archivo in _fechas_existentes(carpeta, patron).items():
        if (hoy - fecha).days > dias:
            archivo.unlink()
            log(f'Depurado en Drive (> {dias} días): {archivo.name}')


def main(cierre=False):
    if not BD.exists():
        print(f'ERROR: no se encontró la base de datos en {BD}')
        return 1

    hoy = date.today()
    ahora = datetime.now()
    dir_diarios = DIR_RESPALDOS / 'diarios'
    dir_semanales = DIR_RESPALDOS / 'semanales'
    dir_anuales = DIR_RESPALDOS / 'anuales'
    drive = _dir_drive()

    # ── DIARIO ──────────────────────────────────────────────────────────
    archivo_dia = dir_diarios / f'pernotodo_{hoy}.db'
    if cierre or not archivo_dia.exists():
        respaldar(archivo_dia)   # con --cierre se actualiza con lo del día completo
    _conservar_ultimos(dir_diarios, PATRON_DIARIO, 7)

    # ── SEMANAL (viernes ≥17:00, o recuperación si pasaron >7 días) ─────
    semanales = _fechas_existentes(dir_semanales, PATRON_SEMANAL)
    ultimo = max(semanales) if semanales else None
    es_viernes_tarde = hoy.weekday() == 4 and ahora.hour >= 17
    atrasado = ultimo is None or (hoy - ultimo).days > 7
    archivo_semana = dir_semanales / f'pernotodo_semana_{hoy}.db'
    if (es_viernes_tarde or atrasado) and not archivo_semana.exists():
        respaldar(archivo_semana)
    _conservar_ultimos(dir_semanales, PATRON_SEMANAL, 8)

    # Copia semanal a Google Drive (se sube sola cuando haya internet)
    if drive:
        try:
            drive.mkdir(parents=True, exist_ok=True)
            for fecha, archivo in _fechas_existentes(dir_semanales, PATRON_SEMANAL).items():
                destino = drive / archivo.name
                if not destino.exists():
                    shutil.copy2(archivo, destino)
                    log(f'Copiado a Drive: {archivo.name}')
            _depurar_por_dias(drive, PATRON_SEMANAL, 90)
        except OSError as e:
            log(f'AVISO: no se pudo copiar a Drive ({e})')
    else:
        log('AVISO: carpeta de Google Drive no encontrada; respaldo en nube omitido.')

    # ── ANUAL (31 de diciembre; recuperación en enero) ──────────────────
    anio_objetivo = None
    if hoy.month == 12 and hoy.day == 31:
        anio_objetivo = hoy.year
    elif hoy.month == 1 and not (dir_anuales / f'pernotodo_{hoy.year - 1}.db').exists():
        anio_objetivo = hoy.year - 1
    if anio_objetivo:
        archivo_anual = dir_anuales / f'pernotodo_{anio_objetivo}.db'
        if not archivo_anual.exists():
            respaldar(archivo_anual)
            if drive:
                try:
                    shutil.copy2(archivo_anual, drive / archivo_anual.name)
                    log(f'Anual copiado a Drive: {archivo_anual.name}')
                except OSError as e:
                    log(f'AVISO: anual no copiado a Drive ({e})')

    log('Respaldo finalizado correctamente.')
    return 0


if __name__ == '__main__':
    sys.exit(main(cierre='--cierre' in sys.argv))
