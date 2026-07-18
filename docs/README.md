# PERNO TODO — Sistema de Gestión de Inventario y Ventas

## Descripción
Sistema web de gestión de inventario, ventas y clientes para el almacén **PERNO TODO**, especializado en ferretería y pernos industriales. Desarrollado con Flask y SQLite.

## Estructura del Proyecto
```
PERNO TODO/
├── app.py                        ← Aplicación principal Flask (rutas y lógica)
├── requirements.txt              ← Dependencias Python
├── render.yaml                   ← Configuración de despliegue en Render.com
├── .gitignore
├── .env                          ← Variables de entorno (NO subir a Git)
│
├── database/
│   ├── connection.py             ← get_db(), init_db(), migrate_db()
│   └── pernotodo.db              ← SQLite (se genera al iniciar; NO subir a Git)
│
├── static/
│   ├── css/style.css
│   └── images/
│
├── templates/
│   ├── base.html                 ← Layout base (sidebar, CSRF, tema claro/oscuro)
│   ├── login.html
│   ├── dashboard.html
│   ├── productos/  proveedores/  clientes/  ventas/
│   ├── egresos/  categorias/  sucursales/  usuarios/
│   ├── reportes/
│   └── errors/                   ← 404 / 500
│
└── docs/
    └── README.md
```

## Instalación Local
```bash
# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno (copiar y editar)
#    SECRET_KEY es OBLIGATORIA. Generar una con:
#    python -c "import secrets; print(secrets.token_hex(32))"

# 4. Ejecutar (la BD se crea/migra automáticamente)
python app.py
```
Abre http://localhost:5000

## Seguridad
- Contraseñas con hash **scrypt/pbkdf2** (Werkzeug). Los hashes antiguos se
  migran automáticamente al formato seguro en el primer inicio de sesión.
- Protección **CSRF** en todos los formularios y APIs POST.
- Bloqueo de login tras 5 intentos fallidos en 5 minutos.
- ⚠️ Cambia las contraseñas de los usuarios semilla antes de usar en producción.

## Facturación
- Los precios de venta **incluyen IVA**. Cada venta guarda el desglose:
  subtotal (base imponible), IVA (`IVA_PCT`, por defecto 15 %) y descuento.
- Las ventas pueden **anularse** (solo Administrador): el stock se repone
  automáticamente y la venta queda excluida de reportes e ingresos.
- Pendiente (no implementado): facturación electrónica SRI (XML firmado / RIDE).
  El sistema emite notas de venta.

## Respaldos
La base es un solo archivo: `database/pernotodo.db`. Respáldalo con frecuencia
(copia a un disco externo o nube). Antes de cualquier migración el sistema
debería respaldarse manualmente.

## Despliegue en Render.com
1. Sube el proyecto a GitHub (sin `.env` ni `venv/`)
2. Crea un nuevo **Web Service** en [render.com](https://render.com)
3. Conecta el repositorio — Render detecta `render.yaml` automáticamente
4. ⚠️ El disco persistente para SQLite requiere **plan pago** (starter).
   Con el plan gratuito la base de datos se borra en cada deploy.

## Tecnologías
- **Python 3.11+** con **Flask 2.3**
- **SQLite** (desarrollo) → migrable a **PostgreSQL** (producción)
- **Bootstrap 5.3** + **Bootstrap Icons**
- **Gunicorn** como servidor WSGI en producción

## Módulos del Sistema
| Módulo | Roles con Acceso |
|---|---|
| Dashboard | Todos |
| Punto de Venta | Admin, Vendedor |
| Historial de Ventas / Anulación | Admin, Vendedor / Solo Admin |
| Egresos / Gastos | Admin, Vendedor (eliminar: solo Admin) |
| Catálogo de Productos | Todos |
| CRUD Productos / Categorías | Solo Administrador |
| Proveedores | Admin (CRUD), Vendedor (solo ver) |
| Clientes | Admin, Vendedor |
| Usuarios / Sucursales / Reportes | Solo Administrador |
