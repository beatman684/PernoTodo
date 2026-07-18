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
│   ├── __init__.py
│   ├── connection.py             ← get_db(), init_db() — todas las tablas
│   └── pernotodo.db              ← SQLite (se genera al iniciar)
│
├── models/
│   ├── __init__.py
│   ├── producto.py
│   ├── cliente.py
│   ├── proveedor.py
│   ├── usuario.py
│   └── venta.py
│
├── static/
│   ├── css/style.css
│   ├── images/
│   └── js/
│
├── templates/
│   ├── base.html                 ← Layout base con navbar
│   ├── login.html
│   ├── dashboard.html
│   ├── productos/
│   │   ├── lista.html
│   │   ├── agregar.html
│   │   └── editar.html
│   ├── proveedores/
│   │   ├── lista.html
│   │   ├── agregar.html
│   │   └── editar.html
│   ├── clientes/
│   │   ├── lista.html
│   │   ├── agregar.html
│   │   └── editar.html
│   ├── ventas/
│   │   ├── punto_de_venta.html
│   │   ├── historial.html
│   │   └── detalle.html
│   ├── usuarios/
│   │   ├── lista.html
│   │   └── agregar.html
│   └── reportes/
│       └── index.html
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

# 3. Ejecutar (la BD se crea automáticamente)
python app.py
```
Abre http://localhost:5000

## Credenciales de Prueba
| Email | Contraseña | Rol |
|---|---|---|
| admin@pernotodo.com | Admin2024 | Administrador |
| vendedor@pernotodo.com | Vende2024 | Vendedor |

## Despliegue en Render.com
1. Sube el proyecto a GitHub (sin `.env` ni `venv/`)
2. Crea un nuevo **Web Service** en [render.com](https://render.com)
3. Conecta el repositorio
4. Render detecta `render.yaml` automáticamente
5. En **Environment Variables** agrega `SECRET_KEY` con una clave segura

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
| Historial de Ventas | Admin, Vendedor |
| Catálogo de Productos | Todos |
| CRUD Productos | Solo Administrador |
| Proveedores | Admin (CRUD), Vendedor (solo ver) |
| Clientes | Admin, Vendedor |
| Usuarios | Solo Administrador |
| Reportes | Solo Administrador |
