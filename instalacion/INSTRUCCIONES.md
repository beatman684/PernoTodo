# Instalación de PERNO TODO en la computadora del negocio

Tiempo estimado: **30–45 minutos**. Solo se hace una vez.

## Antes de empezar — llevar en un USB

Desde la computadora actual (desarrollo), copiar al USB:

1. `database\pernotodo.db` — **todos los datos** (productos, ventas, clientes).
2. `.env` — las claves del sistema *(opcional: si no se copia, el instalador
   genera uno nuevo con clave segura y no pasa nada)*.

## Paso 1 — Instalar los programas base (una sola vez)

En la computadora del negocio, descargar e instalar:

| Programa | De dónde | Detalle importante |
|---|---|---|
| **Python 3.11 o superior** | python.org | ✅ Marcar **"Add Python to PATH"** al instalar |
| **Git** | git-scm.com | Instalación siguiente-siguiente |
| **Google Drive para escritorio** | google.com/drive/download | Ver "Registro del correo" abajo |

## Paso 2 — Descargar el sistema

Abrir el **Símbolo del sistema** (cmd) y ejecutar:

```
cd C:\
git clone https://github.com/beatman684/PernoTodo
```

Queda creada la carpeta `C:\PernoTodo`.

## Paso 3 — Copiar los datos del USB

- Copiar `pernotodo.db` del USB a `C:\PernoTodo\database\` (reemplazar si pregunta).
- Copiar `.env` del USB a `C:\PernoTodo\` (si se llevó).

## Paso 4 — Instalar

- Doble clic en `C:\PernoTodo\instalacion\instalar.bat` → espera a "INSTALACIÓN COMPLETADA".
- Clic **derecho** en `C:\PernoTodo\instalacion\configurar_tareas.bat` →
  **"Ejecutar como administrador"**.
- Reiniciar la computadora.

## Paso 5 — Comprobar

Al encender, después de ~1 minuto, abrir el ícono **PERNO TODO** del escritorio.
Debe aparecer la pantalla de inicio de sesión. ✅ Listo para vender.

---

## 📧 Registro del correo para los respaldos en la nube

Los respaldos NO usan contraseñas dentro del sistema: se apoyan en la app
oficial **Google Drive para escritorio**, así:

1. Instalar **Google Drive para escritorio** (google.com/drive/download).
2. Al abrirla pide iniciar sesión → usar **el correo del dueño** y su contraseña
   (la escribe el dueño directamente en la ventana de Google, nadie más la ve
   ni queda guardada en PERNO TODO).
3. Con eso aparece una unidad `G:\Mi unidad` en el equipo. **Nada más que hacer**:
   el sistema detecta la carpeta solo y deja allí los respaldos semanales;
   Google los sube automáticamente cuando haya internet.
4. Si Drive quedara en otra ruta, se indica en el archivo `.env`:
   `RUTA_DRIVE=D:\la\ruta\que\sea`

## Cómo queda funcionando el día a día

| Momento | Qué pasa (automático) |
|---|---|
| Encender la PC | El sistema arranca solo + respaldo diario (guarda 7 días) |
| Viernes 6:00 PM | Respaldo semanal en disco (8 semanas) + copia a Drive (3 meses) |
| Cerrar con el botón **"Cerrar PERNO TODO"** | Mensaje "no apague el equipo" → respaldo → apaga la PC sola |
| 31 de diciembre | Respaldo anual permanente (disco + Drive) |

- **Vender**: ícono "PERNO TODO" del escritorio → iniciar sesión → Punto de Venta.
- **Actualizar el sistema**: ícono "Actualizar PERNO TODO" (necesita internet, 1 min).
- **Ver desde el celular** (misma red WiFi): en el navegador del celular ir a
  `http://IP-DE-LA-PC:5000` (la IP se ve con el comando `ipconfig`).
- Los respaldos quedan en `C:\Respaldos_PernoTodo\` (diarios / semanales / anuales)
  y el registro de cada respaldo en `respaldo.log`.

## Primer día de uso (importante)

1. Entrar como administrador y **cambiar las contraseñas** de los dos usuarios.
2. Eliminar el usuario antiguo `admin@admin.com` (módulo Usuarios).
3. Hacer el conteo físico de stock y corregir cantidades (módulo Productos).
