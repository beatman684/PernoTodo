import sqlite3
import os
import hashlib

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pernotodo.db')


def get_db():
    conn = sqlite3.connect(DATABASE, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 8000")
    return conn


def _hash(password, length=24):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()[:length]


def migrate_db():
    """
    Aplica todas las migraciones necesarias al esquema existente.
    Se ejecuta cada vez que arranca la app. Es idempotente.
    """
    try:
        db = get_db()
        cur = db.cursor()

        # 1. Renombrar password_hash → password (BD vieja)
        ucols = [c['name'] for c in cur.execute("PRAGMA table_info(usuario)").fetchall()]
        if 'password_hash' in ucols and 'password' not in ucols:
            cur.execute("ALTER TABLE usuario RENAME COLUMN password_hash TO password")
            db.commit()

        # 2. Añadir columna 'tipo' a clientes si falta
        ccols = [c['name'] for c in cur.execute("PRAGMA table_info(clientes)").fetchall()]
        if 'tipo' not in ccols:
            cur.execute("ALTER TABLE clientes ADD COLUMN tipo VARCHAR(20) DEFAULT 'minorista'")
            db.commit()

        # 3. Añadir columna 'banco' a ventas si falta
        vcols = [c['name'] for c in cur.execute("PRAGMA table_info(ventas)").fetchall()]
        if 'banco' not in vcols:
            cur.execute("ALTER TABLE ventas ADD COLUMN banco VARCHAR(50)")
            db.commit()

        # 4. Añadir columna 'id_sucursal' a ventas si falta
        if 'id_sucursal' not in vcols:
            cur.execute("ALTER TABLE ventas ADD COLUMN id_sucursal INTEGER DEFAULT 1")
            db.commit()

        # 5. Crear tabla sucursales si no existe
        cur.execute("""CREATE TABLE IF NOT EXISTS sucursales (
            id_sucursal INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre VARCHAR(100) NOT NULL,
            direccion TEXT, telefono VARCHAR(20), ruc VARCHAR(13),
            es_matriz INTEGER DEFAULT 0, activa INTEGER DEFAULT 1,
            fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        db.commit()

        # 6. Insertar sucursal matriz si no existe
        if cur.execute("SELECT COUNT(*) FROM sucursales").fetchone()[0] == 0:
            cur.execute("INSERT INTO sucursales (id_sucursal,nombre,es_matriz,activa) VALUES (1,'Matriz',1,1)")
            db.commit()

        # 7. Limpiar categorías duplicadas (problema conocido en BD existente)
        try:
            cur.execute("""
                DELETE FROM categorias WHERE id_categoria NOT IN (
                    SELECT MIN(id_categoria) FROM categorias GROUP BY nombre_categoria
                )
            """)
            # Eliminar variantes con tilde duplicadas (Espárragos vs Esparragos)
            cur.execute("DELETE FROM categorias WHERE nombre_categoria IN ('Espárragos','Esparragos') AND id_categoria NOT IN (SELECT MIN(id_categoria) FROM categorias WHERE nombre_categoria IN ('Espárragos','Esparragos'))")
            db.commit()
        except Exception:
            pass

        # 8. Crear tabla egresos si no existe
        cur.execute("""CREATE TABLE IF NOT EXISTS egresos (
            id_egreso INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            categoria VARCHAR(50) NOT NULL,
            descripcion TEXT NOT NULL,
            monto DECIMAL(10,2) NOT NULL,
            metodo_pago VARCHAR(30) DEFAULT 'Efectivo',
            banco VARCHAR(50),
            id_proveedor INTEGER,
            id_empleado INTEGER,
            id_sucursal INTEGER DEFAULT 1,
            comprobante VARCHAR(100)
        )""")
        db.commit()

        db.close()
    except Exception as e:
        print(f"[migrate_db] Advertencia: {e}")
        try:
            db.close()
        except Exception:
            pass


def init_db():
    """Crea todas las tablas e inserta datos semilla. Idempotente."""
    migrate_db()
    db = get_db()
    cur = db.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS sucursales (
        id_sucursal INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre VARCHAR(100) NOT NULL,
        direccion TEXT, telefono VARCHAR(20), ruc VARCHAR(13),
        es_matriz INTEGER DEFAULT 0, activa INTEGER DEFAULT 1,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS categorias (
        id_categoria INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre_categoria VARCHAR(80) NOT NULL UNIQUE
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS proveedores (
        id_proveedor INTEGER PRIMARY KEY AUTOINCREMENT,
        ruc VARCHAR(13) NOT NULL UNIQUE, nombre_empresa VARCHAR(150) NOT NULL,
        contacto VARCHAR(100), telefono VARCHAR(20), email VARCHAR(100),
        direccion TEXT, fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS clientes (
        cedula VARCHAR(13) PRIMARY KEY,
        nombres VARCHAR(100) NOT NULL, apellidos VARCHAR(100) NOT NULL,
        telefono VARCHAR(20), email VARCHAR(100), direccion TEXT,
        tipo VARCHAR(20) DEFAULT 'minorista'
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS productos (
        id_producto INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo_producto VARCHAR(20) NOT NULL UNIQUE,
        nombre_producto VARCHAR(150) NOT NULL,
        descripcion TEXT,
        material VARCHAR(50) NOT NULL DEFAULT 'N/A',
        tipo_rosca VARCHAR(30) DEFAULT 'N/A',
        medida VARCHAR(20) NOT NULL DEFAULT 'N/A',
        unidad_medida VARCHAR(10) DEFAULT 'unidad',
        precio_compra DECIMAL(10,2) NOT NULL DEFAULT 0,
        precio_venta DECIMAL(10,2) NOT NULL DEFAULT 0,
        stock_actual INTEGER DEFAULT 0,
        stock_minimo INTEGER DEFAULT 10,
        id_proveedor INTEGER, id_categoria INTEGER,
        fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor),
        FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS usuario (
        id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        nombre VARCHAR(100) NOT NULL DEFAULT 'Usuario',
        role VARCHAR(20) NOT NULL DEFAULT 'Vendedor',
        id_sucursal INTEGER DEFAULT 1
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ventas (
        id_venta INTEGER PRIMARY KEY AUTOINCREMENT,
        cedula_cliente VARCHAR(13) DEFAULT '9999999999',
        id_empleado INTEGER NOT NULL,
        id_sucursal INTEGER DEFAULT 1,
        fecha_venta TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total DECIMAL(10,2) NOT NULL,
        estado VARCHAR(20) DEFAULT 'completada',
        metodo_pago VARCHAR(30) DEFAULT 'Efectivo',
        banco VARCHAR(50),
        FOREIGN KEY (id_empleado) REFERENCES usuario(id_usuario)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS detalle_venta (
        id_detalle INTEGER PRIMARY KEY AUTOINCREMENT,
        id_venta INTEGER NOT NULL, id_producto INTEGER NOT NULL,
        cantidad INTEGER NOT NULL,
        precio_unitario DECIMAL(10,2) NOT NULL,
        subtotal DECIMAL(10,2) NOT NULL,
        FOREIGN KEY (id_venta)    REFERENCES ventas(id_venta),
        FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS egresos (
        id_egreso INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        categoria VARCHAR(50) NOT NULL,
        descripcion TEXT NOT NULL,
        monto DECIMAL(10,2) NOT NULL,
        metodo_pago VARCHAR(30) DEFAULT 'Efectivo',
        banco VARCHAR(50),
        id_proveedor INTEGER,
        id_empleado INTEGER,
        id_sucursal INTEGER DEFAULT 1,
        comprobante VARCHAR(100)
    )""")

    db.commit()

    # Semilla
    cur.execute("INSERT OR IGNORE INTO sucursales (id_sucursal,nombre,es_matriz,activa) VALUES (1,'Matriz',1,1)")
    for cat in ['Pernos','Tornillos','Tuercas','Arandelas','Pernos de Anclaje',
                'Esparragos','Herramientas','Empaques','Materiales','Brocas','Otros']:
        cur.execute("INSERT OR IGNORE INTO categorias (nombre_categoria) VALUES (?)", (cat,))
    for ruc, emp, cont, tel, email, dir_ in [
        ('1790012345001','Pernos Industriales S.A.','Juan Pérez','0987654321','ventas@pernosindustriales.com','Av. Industrial 123, Quito'),
        ('0990098765001','Tornilleria Nacional','Maria Garcia','0976543210','info@tornillerianacional.com','Calle Comercial 456, Guayaquil'),
    ]:
        cur.execute("INSERT OR IGNORE INTO proveedores (ruc,nombre_empresa,contacto,telefono,email,direccion) VALUES (?,?,?,?,?,?)",
                    (ruc,emp,cont,tel,email,dir_))
    for email, pwd, nombre, role in [
        ('admin@pernotodo.com','Admin2024','Juan Administrador','Administrador'),
        ('vendedor@pernotodo.com','Vende2024','Maria Vendedora','Vendedor'),
    ]:
        cur.execute("SELECT id_usuario FROM usuario WHERE email=?", (email,))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO usuario (email,password,nombre,role) VALUES (?,?,?,?)",
                        (email, _hash(pwd), nombre, role))

    db.commit()
    db.close()
    print("Base de datos inicializada correctamente.")


if __name__ == '__main__':
    os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
    init_db()