# PERNO TODO — Sistema de Facturación e Inventario

Sistema web de gestión de inventario, ventas, clientes y caja para el almacén
**PERNO TODO** (Loja, Ecuador), especializado en ferretería y pernos
industriales. Desarrollado con Flask y SQLite.

---

## Estructura del Proyecto

```
PernoTodo/
├── app.py                    ← Aplicación Flask (rutas y lógica de negocio)
├── servidor.py               ← Servidor de producción (Waitress)
├── requirements.txt          ← Dependencias Python
├── requirements-dev.txt      ← Dependencias de pruebas
├── render.yaml               ← Despliegue opcional en Render.com
├── .env                      ← Variables de entorno (NO se sube a Git)
│
├── database/
│   ├── connection.py         ← get_db(), init_db(), migrate_db()
│   └── pernotodo.db          ← Base SQLite (NO se sube a Git)
│
├── scripts/
│   └── respaldo.py           ← Respaldos automáticos con rotación
│
├── tests/
│   └── test_facturacion.py   ← Pruebas de cálculo de totales e IVA
├── .github/workflows/        ← Integración continua (GitHub Actions)
│
├── instalacion/              ← Puesta en marcha en la PC del negocio
│   ├── instalar.bat          ← Instalación completa en un clic
│   ├── iniciar_servidor.vbs  ← Arranque silencioso del servidor
│   ├── crear_icono.ps1       ← Acceso directo del escritorio
│   ├── actualizar.bat        ← Descarga la última versión
│   ├── respaldo_manual.bat   ← Respaldo bajo demanda
│   └── INSTRUCCIONES.md      ← Guía paso a paso de instalación
│
├── static/
│   ├── css/style.css
│   └── images/               ← Logo del negocio (png / ico / favicon)
│
├── templates/
│   ├── base.html             ← Layout (menú, CSRF, tema claro/oscuro)
│   ├── login.html  dashboard.html
│   ├── productos/  proveedores/  clientes/  ventas/
│   ├── egresos/  categorias/  sucursales/  usuarios/
│   ├── reportes/             ← Reportes y Cierre del Día
│   └── errors/               ← 404 / 500
│
└── docs/README.md
```

---

## Requisitos

- **Python 3.11+**
- **Git** (para clonar y actualizar)
- Navegador moderno (Edge o Chrome recomendados)

---

## Instalación

### En la computadora del negocio (producción)

Doble clic en `instalacion\instalar.bat`. Instala dependencias, genera la
clave de seguridad, programa el arranque automático y los respaldos, y crea
el acceso directo del escritorio.

Guía completa: **[instalacion/INSTRUCCIONES.md](../instalacion/INSTRUCCIONES.md)**

### Entorno de desarrollo

```bash
python -m venv venv
venv\Scripts\activate                 # Windows
python -m pip install -r requirements.txt
python app.py                         # servidor de desarrollo
```

Abre http://localhost:5000 · En producción se usa `python servidor.py`
(Waitress), que es el que arranca automáticamente con el equipo.

> La base de datos se crea y migra sola al iniciar. Las migraciones son
> idempotentes: nunca destruyen datos existentes.

---

## Variables de entorno (`.env`)

| Variable | Por defecto | Descripción |
|---|---|---|
| `SECRET_KEY` | — | **Obligatoria.** Clave de sesión. Generar con `python -c "import secrets; print(secrets.token_hex(32))"` |
| `IVA_PCT` | `15` | Porcentaje de IVA aplicado al desglose |
| `HORA_CORTE` | `20` | Hora de corte del día de negocio (8:00 PM) |
| `FLASK_DEBUG` | `false` | Modo depuración (solo desarrollo) |
| `RUTA_RESPALDOS` | `C:\Respaldos_PernoTodo` | Carpeta local de respaldos |
| `RUTA_DRIVE` | autodetectado | Carpeta de Google Drive para respaldo en nube |

---

## Día de negocio y Cierre del Día

El sistema agrupa las operaciones por **día de negocio**, no por fecha del
reloj:

- Las ventas y egresos posteriores a las **20:00** (`HORA_CORTE`) se
  registran para el día siguiente.
- El botón rojo **CIERRE DEL DÍA** genera el reporte de caja: efectivo que
  debe haber en caja, resumen por método de pago con desglose por banco o
  aplicación (Ahorita, De Una, tarjetas), detalle de ventas y egresos, IVA
  y resultado del día, con líneas de firma entregado/recibido.
- **CERRAR EL DÍA E IMPRIMIR** imprime el cierre (formato de impresora
  térmica 80 mm), registra el día como cerrado y ejecuta un respaldo. Las
  ventas posteriores pasan al día siguiente aunque no sean las 8 PM.

---

## Códigos de producto

Se generan automáticamente combinando **categoría + tipo de rosca +
correlativo**, y el formulario muestra los códigos ya usados de la serie
para mantener el orden:

| Producto | Código |
|---|---|
| Perno rosca **Fina** | `PER-F1`, `PER-F2`… |
| Perno **Milimétrica** | `PER-M1`, `PER-M2`… |
| Perno rosca **Gruesa** | `PER-G1`, `PER-G2`… |
| Sin rosca (brocas, empaques…) | `BRO-001`, `EMP-001`… |

El código manual sigue disponible. Cada producto puede imprimir su etiqueta
con código de barras (CODE128), nombre, medida y precio.

---

## Pruebas automatizadas

```bash
python -m pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Cubren el cálculo de totales del punto de venta: desglose de IVA, aplicación
de descuentos y validación de sus límites (un descuento negativo se ajusta a
0 % y uno mayor a 100 se limita a 100 %), además del IVA configurable.

Las pruebas se ejecutan automáticamente en **GitHub Actions** con cada envío
de cambios al repositorio (`.github/workflows/tests.yml`).

---

## Facturación

- Los precios de venta **incluyen IVA**. Cada venta guarda el desglose:
  subtotal (base imponible), IVA y descuento.
- Las ventas pueden **anularse** (solo Administrador): el stock se repone
  automáticamente y la venta queda excluida de ingresos y reportes.
- **No implementado:** facturación electrónica del SRI (XML firmado / RIDE).
  El sistema emite notas de venta.

---

## Seguridad

- Contraseñas con hash **scrypt** (Werkzeug). Los hashes en formato antiguo
  se migran automáticamente al iniciar sesión.
- Protección **CSRF** en todos los formularios y peticiones POST.
- Bloqueo de acceso tras **5 intentos fallidos** en 5 minutos.
- Sesión con expiración de 8 horas; cookies `HttpOnly` y `SameSite=Lax`.
- Consultas SQL parametrizadas y control de acceso por rol en cada ruta.

> ⚠️ Cambia las contraseñas de los usuarios iniciales antes de poner el
> sistema en operación.

---

## Respaldos

La base de datos es un solo archivo (`database/pernotodo.db`). El script
`scripts/respaldo.py` mantiene esta rotación de forma automática:

| Tipo | Cuándo | Dónde | Se conservan |
|---|---|---|---|
| Diario | Al encender el equipo | Disco | 7 días |
| Semanal | Viernes 18:00 | Disco + Google Drive | 8 semanas / 90 días |
| Anual | 31 de diciembre | Disco + Google Drive | Permanente |

Las copias se hacen con la API `backup` de SQLite, por lo que son
consistentes aunque el sistema esté en uso. Registro en `respaldo.log`.

---

## Despliegue en Render.com (opcional)

1. Subir el proyecto a GitHub (sin `.env` ni `venv/`).
2. Crear un **Web Service** y conectar el repositorio; Render detecta
   `render.yaml` automáticamente.
3. ⚠️ El disco persistente para SQLite requiere **plan pago** (starter). Con
   el plan gratuito la base de datos se borra en cada despliegue.

---

## Tecnologías

- **Python 3.11+** con **Flask 2.3**
- **SQLite** (migrable a PostgreSQL)
- **Waitress** como servidor de producción en Windows (Gunicorn en Render)
- **Bootstrap 5.3** + **Bootstrap Icons**
- **JsBarcode** para códigos de barras en etiquetas

---

## Módulos y permisos

| Módulo | Administrador | Vendedor |
|---|---|---|
| Dashboard | ✅ | ✅ |
| Punto de Venta | ✅ | ✅ |
| Historial de Ventas | ✅ | ✅ |
| Anular venta | ✅ | ❌ |
| Cierre del Día | ✅ | ✅ |
| Egresos / Gastos | ✅ | ✅ (no puede eliminar) |
| Consultar productos y clientes | ✅ | ✅ |
| Crear / editar / eliminar productos | ✅ | ❌ |
| Proveedores | ✅ | Solo consulta |
| Categorías · Sucursales · Usuarios · Reportes | ✅ | ❌ |

---

## Flujo de trabajo con Git

El proyecto sigue **GitHub Flow**: la rama `main` se mantiene siempre estable
y desplegable; cada cambio se desarrolla en una rama `feature/*` independiente
y se integra a `main` mediante un **Pull Request**, lo que permite revisar los
cambios antes de fusionarlos y deja registro del historial de cada aporte.

```bash
git checkout -b feature/nombre-del-cambio   # 1. Crear la rama
git commit -m "Descripción del cambio"      # 2. Confirmar los cambios
git push origin feature/nombre-del-cambio   # 3. Publicar la rama
# 4. Abrir el Pull Request hacia main y fusionarlo tras la revisión
```
