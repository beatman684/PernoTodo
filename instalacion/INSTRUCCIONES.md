# Instalación de PERNO TODO en la computadora del negocio

Tiempo estimado: **30 minutos**. Solo se hace una vez.

## Antes de empezar — llevar en un USB

Desde la computadora actual (desarrollo), copiar al USB:

1. `database\pernotodo.db` — **todos los datos** (productos, ventas, clientes).
2. `.env` — las claves del sistema *(opcional: si no se copia, el instalador
   genera uno nuevo con clave segura y no pasa nada)*.

## Paso 1 — Instalar los programas base (una sola vez)

| Programa | De dónde | Detalle importante |
|---|---|---|
| **Python 3.11 o superior** | python.org | ✅ Marcar **"Add Python to PATH"** al instalar |
| **Git** | git-scm.com | Instalación siguiente-siguiente |
| **Google Drive para escritorio** | google.com/drive/download | Ver "Registro del correo" abajo |
| **Driver de la impresora térmica** | CD o web del fabricante | Ponerla como **impresora predeterminada** de Windows |

## Paso 2 — Descargar el sistema

Abrir el **Símbolo del sistema** (cmd) y ejecutar:

```
cd C:\
git clone https://github.com/beatman684/PernoTodo
```

## Paso 3 — Copiar los datos del USB

- `pernotodo.db` del USB → `C:\PernoTodo\database\` (reemplazar si pregunta).
- `.env` del USB → `C:\PernoTodo\` (si se llevó).

## Paso 4 — Instalar (UN SOLO CLIC)

Doble clic en `C:\PernoTodo\instalacion\instalar.bat` → aceptar el permiso de
administrador → esperar a "INSTALACIÓN COMPLETADA" → **reiniciar la PC**.

Eso hace TODO: dependencias, clave de seguridad, arranque automático,
respaldos programados, acceso desde la red local y el **ícono PERNO TODO**
(con el logo del negocio) en el escritorio.

## Paso 5 — Comprobar

Al encender, después de ~1 minuto, doble clic al ícono **PERNO TODO**.
Se abre en ventana propia (sin barras de navegador) y con impresión directa
a la térmica. ✅ Listo para vender.

---

## 📧 Registro del correo para los respaldos en la nube

Los respaldos NO usan contraseñas dentro de PERNO TODO:

1. Instalar **Google Drive para escritorio**.
2. Al abrirla, el **dueño** inicia sesión con su correo directamente en la
   ventana de Google (nadie más ve la contraseña, no queda en el sistema).
3. Aparece la unidad `G:\Mi unidad` — **nada más que configurar**: el sistema
   detecta la carpeta solo y Google sube los respaldos cuando haya internet.
4. Si Drive quedara en otra ruta: indicarla en `.env` → `RUTA_DRIVE=...`

## El día a día

| Momento | Qué pasa |
|---|---|
| Encender la PC | El sistema arranca solo + respaldo diario (guarda 7 días) |
| Vender | Ícono **PERNO TODO** → iniciar sesión → Punto de Venta |
| Fin del día | Botón rojo **CIERRE DEL DÍA** → "CERRAR EL DÍA E IMPRIMIR": imprime el cierre en la térmica, respalda, y pregunta *"¿Cerrar el programa? Sí/No"* (se cierra solo en 60 s). Las ventas posteriores cuentan para el día siguiente |
| Viernes 6:00 PM | Respaldo semanal en disco (8 semanas) + Drive (3 meses), automático |
| Corte automático | Las ventas después de las **8:00 PM** se registran para el día siguiente (configurable con `HORA_CORTE` en `.env`) |

## Herramientas en `instalacion\` (para el dueño, no van al escritorio)

- `actualizar.bat` — baja la última versión desde GitHub (1 min, con internet).
- `respaldo_manual.bat` — hace un respaldo al instante.
- `crear_icono.ps1` — vuelve a crear el ícono del escritorio si se borra.

Los respaldos quedan en `C:\Respaldos_PernoTodo\` y su registro en `respaldo.log`.
Ver desde el celular (misma WiFi): `http://IP-DE-LA-PC:5000` (IP con `ipconfig`).

## Primer día de uso (importante)

1. Entrar como administrador y **cambiar las contraseñas** de los dos usuarios.
2. Eliminar el usuario antiguo `admin@admin.com` (módulo Usuarios).
3. Conteo físico de stock y corregir cantidades (módulo Productos).
