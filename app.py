import sqlite3
import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, g, jsonify)
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db, init_db, migrate_db

load_dotenv()

app = Flask(__name__)
_secret = os.environ.get('SECRET_KEY')
if not _secret:
    # Sin SECRET_KEY en el entorno: se genera una temporal (las sesiones se
    # invalidan al reiniciar). En producción SIEMPRE definir SECRET_KEY.
    _secret = secrets.token_hex(32)
    app.logger.warning('SECRET_KEY no definida en el entorno; usando clave temporal.')
app.config['SECRET_KEY'] = _secret
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# IVA vigente en Ecuador (%). Los precios de venta INCLUYEN IVA;
# el sistema desglosa subtotal e IVA a partir del total.
IVA_PCT = float(os.environ.get('IVA_PCT', '15'))

_PREFIJOS = {
    'pernos': 'PER', 'tornillos': 'TOR', 'tuercas': 'TUE',
    'arandelas': 'ARR', 'pernos de anclaje': 'ANC', 'esparragos': 'ESP',
    'herramientas': 'HER', 'empaques': 'EMP', 'clavos': 'CLA',
    'materiales': 'MAT', 'brocas': 'BRO', 'otros': 'OTR',
}

BANCOS_EC = [
    'Banco Pichincha', 'Banco Guayaquil', 'Banco Pacífico',
    'Banco Internacional', 'Banco Bolivariano', 'Banco Produbanco',
    'Banco del Austro', 'Banco Solidario', 'Cooperativa JEP',
    'Cooperativa 29 de Octubre', 'Diners Club', 'Mastercard',
    'Visa', 'Efectivo', 'Otro',
]

CATEGORIAS_EGRESO = [
    'Pago a Proveedor', 'Pago Personal', 'Servicios Básicos',
    'Arriendo', 'Transporte', 'Mantenimiento', 'Insumos',
    'Depósito / Cheque', 'Impuestos', 'Otros Gastos',
]


def _prefijo_cat(nombre):
    lw = nombre.lower().strip()
    for k, v in _PREFIJOS.items():
        if k in lw:
            return v
    letras = ''.join(c for c in nombre.upper() if c.isalpha())
    return letras[:3].ljust(3, 'X')


def hash_password(p):
    return generate_password_hash(p)


def _legacy_hash(p):
    # Formato antiguo: SHA-256 truncado a 24 caracteres (solo para compatibilidad)
    return hashlib.sha256(p.encode('utf-8')).hexdigest()[:24]


def verificar_password(stored, pwd):
    """Devuelve (ok, es_legacy). Acepta hashes nuevos (werkzeug) y antiguos."""
    if not stored:
        return False, False
    if ':' in stored:  # formato werkzeug: metodo:sal:hash / metodo$sal$hash
        try:
            return check_password_hash(stored, pwd), False
        except Exception:
            return False, False
    if '$' in stored:
        try:
            return check_password_hash(stored, pwd), False
        except Exception:
            return False, False
    return hmac.compare_digest(stored, _legacy_hash(pwd)), True


def _safe_next(n):
    if n and n.startswith('/') and not n.startswith('//'):
        return n
    return url_for('dashboard')


# ── LÍMITE DE INTENTOS DE LOGIN (anti fuerza bruta) ─────────────────────────
_login_fails = defaultdict(list)   # clave → [timestamps de fallos]
LOGIN_MAX_FAILS = 5
LOGIN_WINDOW_S  = 300  # 5 minutos


def _login_bloqueado(clave):
    ahora = time.time()
    _login_fails[clave] = [t for t in _login_fails[clave] if ahora - t < LOGIN_WINDOW_S]
    return len(_login_fails[clave]) >= LOGIN_MAX_FAILS


def _login_fallo(clave):
    _login_fails[clave].append(time.time())


# ── PROTECCIÓN CSRF ─────────────────────────────────────────────────────────
def _csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_hex(16)
    return session['_csrf']


@app.context_processor
def inject_csrf():
    return {'csrf_token': _csrf_token}


@app.before_request
def csrf_protect():
    if request.method == 'POST':
        token = session.get('_csrf', '')
        enviado = request.form.get('csrf_token') or request.headers.get('X-CSRFToken', '')
        if not token or not hmac.compare_digest(token, enviado):
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({'success': False,
                                'message': 'Sesión inválida o expirada. Recarga la página.'}), 400
            flash('Sesión inválida o expirada. Intenta de nuevo.', 'danger')
            return redirect(request.referrer or url_for('dashboard'))


# ── MIDDLEWARE ──────────────────────────────────────────────────────────────
@app.before_request
def load_user():
    session.permanent = True
    g.user  = None
    g.theme = session.get('theme', 'light')
    email   = session.get('email')
    if email:
        db  = get_db()
        row = db.execute(
            "SELECT id_usuario, email, nombre, role FROM usuario WHERE email=?", (email,)
        ).fetchone()
        db.close()
        if row:
            g.user = dict(row)
        else:
            session.clear()


# ── DECORADORES ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if not g.user:
            flash('Inicia sesión para continuar.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*a, **k)
    return w


def role_required(*roles):
    def dec(f):
        @wraps(f)
        def w(*a, **k):
            if not g.user:
                return redirect(url_for('login'))
            if g.user.get('role') not in roles:
                flash('Sin permisos.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*a, **k)
        return w
    return dec


admin_required = role_required('Administrador')


# ── ERRORES ─────────────────────────────────────────────────────────────────
@app.errorhandler(404)
def e404(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(500)
def e500(e):
    return render_template('errors/500.html'), 500


# ── TEMA ────────────────────────────────────────────────────────────────────
@app.route('/set_theme/<theme>')
def set_theme(theme):
    if theme in ('light', 'dark'):
        session['theme'] = theme
    return redirect(request.referrer or url_for('dashboard'))


# ── AUTH ────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.user:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pwd   = request.form.get('password', '')
        clave = f'{request.remote_addr}|{email}'
        if _login_bloqueado(clave):
            flash('Demasiados intentos fallidos. Espera 5 minutos.', 'danger')
            return render_template('login.html')
        db   = get_db()
        user = db.execute(
            "SELECT * FROM usuario WHERE email=?", (email,)
        ).fetchone()
        stored = user['password'] if user else None
        ok, es_legacy = verificar_password(stored, pwd)
        if ok and es_legacy:
            # Migrar el hash antiguo al formato seguro de forma transparente
            db.execute("UPDATE usuario SET password=? WHERE id_usuario=?",
                       (hash_password(pwd), user['id_usuario']))
            db.commit()
        db.close()
        if ok:
            _login_fails.pop(clave, None)
            session.clear()
            session['email'] = user['email']
            _csrf_token()
            return redirect(_safe_next(request.args.get('next')))
        _login_fallo(clave)
        flash('Email o contraseña incorrectos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ── DASHBOARD ───────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/dashboard')
@login_required
def dashboard():
    stats = dict(total_productos=0, bajo_stock=0, total_proveedores=0,
                 ventas_hoy=0, ingresos_hoy=0.0, ventas_mes=0.0,
                 total_clientes=0, ventas_7dias=[], egresos_hoy=0.0)
    alertas = []
    ultimas_ventas = []
    try:
        db = get_db()
        stats['total_productos']   = db.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
        stats['bajo_stock']        = db.execute("SELECT COUNT(*) FROM productos WHERE stock_actual<stock_minimo").fetchone()[0]
        stats['total_proveedores'] = db.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0]
        stats['total_clientes']    = db.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
        r = db.execute("SELECT COUNT(*) c, COALESCE(SUM(total),0) s FROM ventas WHERE DATE(fecha_venta)=DATE('now') AND estado='completada'").fetchone()
        stats['ventas_hoy']   = r['c']
        stats['ingresos_hoy'] = r['s']
        stats['ventas_mes']   = db.execute(
            "SELECT COALESCE(SUM(total),0) FROM ventas WHERE strftime('%Y-%m',fecha_venta)=strftime('%Y-%m','now') AND estado='completada'"
        ).fetchone()[0]
        stats['egresos_hoy']  = db.execute(
            "SELECT COALESCE(SUM(monto),0) FROM egresos WHERE DATE(fecha)=DATE('now')"
        ).fetchone()[0]
        alertas = db.execute(
            "SELECT nombre_producto,stock_actual,stock_minimo FROM productos WHERE stock_actual<stock_minimo ORDER BY (stock_actual-stock_minimo) LIMIT 8"
        ).fetchall()
        ventas_7 = db.execute(
            "SELECT DATE(fecha_venta) dia, SUM(total) total FROM ventas WHERE fecha_venta>=DATE('now','-6 days') AND estado='completada' GROUP BY dia ORDER BY dia"
        ).fetchall()
        stats['ventas_7dias'] = [dict(r) for r in ventas_7]
        ultimas_ventas = db.execute(
            "SELECT v.id_venta,v.fecha_venta,v.total,v.metodo_pago,COALESCE(c.nombres||' '||c.apellidos,'Público General') nombre_cliente FROM ventas v LEFT JOIN clientes c ON v.cedula_cliente=c.cedula ORDER BY v.fecha_venta DESC LIMIT 5"
        ).fetchall()
        db.close()
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return render_template('dashboard.html', stats=stats, alertas=alertas,
                           ultimas_ventas=ultimas_ventas, now=datetime.now())


# ── PUNTO DE VENTA ──────────────────────────────────────────────────────────
@app.route('/punto_de_venta')
@role_required('Administrador', 'Vendedor')
def punto_de_venta():
    return render_template('ventas/punto_de_venta.html', bancos=BANCOS_EC)


@app.route('/api/buscar_productos')
@role_required('Administrador', 'Vendedor')
def buscar_productos_api():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify([])
    term = f'%{q}%'
    db = get_db()
    rows = db.execute(
        "SELECT id_producto,codigo_producto,nombre_producto,precio_venta,stock_actual,medida FROM productos WHERE (codigo_producto LIKE ? OR nombre_producto LIKE ?) AND stock_actual>0 LIMIT 15",
        (term, term)
    ).fetchall()
    db.close()
    return jsonify([{'id':r['id_producto'],'codigo':r['codigo_producto'],'nombre':r['nombre_producto'],
                     'precio':float(r['precio_venta']),'stock':r['stock_actual'],'medida':r['medida'] or ''} for r in rows])


@app.route('/api/buscar_cliente')
@role_required('Administrador', 'Vendedor')
def buscar_cliente_api():
    cedula = request.args.get('cedula', '').strip()
    if len(cedula) < 3:
        return jsonify(None)
    db = get_db()
    c = db.execute("SELECT * FROM clientes WHERE cedula=?", (cedula,)).fetchone()
    db.close()
    return jsonify(dict(c) if c else None)


@app.route('/api/guardar_cliente_rapido', methods=['POST'])
@role_required('Administrador', 'Vendedor')
def guardar_cliente_rapido():
    data = request.get_json(silent=True) or {}
    cedula    = data.get('cedula', '').strip()
    nombres   = data.get('nombres', '').strip()
    apellidos = data.get('apellidos', '').strip()
    telefono  = data.get('telefono', '').strip()
    email     = data.get('email', '').strip()
    direccion = data.get('direccion', '').strip()
    # La BD real tiene telefono y direccion NOT NULL — usar 'N/A' si están vacíos
    if not telefono: telefono = 'N/A'
    if not direccion: direccion = 'N/A'
    if not apellidos: apellidos = 'N/A'
    if not cedula or not nombres:
        return jsonify({'success': False, 'message': 'Cédula y nombres son obligatorios.'}), 400
    db = None
    try:
        db = get_db()
        cols = [c['name'] for c in db.execute("PRAGMA table_info(clientes)").fetchall()]
        if 'tipo' in cols:
            db.execute(
                "INSERT OR REPLACE INTO clientes (cedula,nombres,apellidos,telefono,email,direccion,tipo) VALUES (?,?,?,?,?,?,?)",
                (cedula, nombres, apellidos, telefono, email, direccion, 'minorista'))
        else:
            db.execute(
                "INSERT OR REPLACE INTO clientes (cedula,nombres,apellidos,telefono,email,direccion) VALUES (?,?,?,?,?,?)",
                (cedula, nombres, apellidos, telefono, email, direccion))
        db.commit()
        return jsonify({'success': True})
    except sqlite3.Error as e:
        if db:
            try: db.rollback()
            except Exception: pass
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if db:
            try: db.close()
            except Exception: pass


@app.route('/api/finalizar_venta', methods=['POST'])
@role_required('Administrador', 'Vendedor')
def finalizar_venta():
    db = None
    try:
        data          = request.get_json(silent=True) or {}
        carrito       = data.get('carrito', [])
        cedula        = (data.get('cedula_cliente') or '9999999999').strip()
        metodo_pago   = data.get('metodo_pago', 'Efectivo')
        banco         = data.get('banco', '').strip() or None
        descuento_pct = float(data.get('descuento', 0) or 0)

        if metodo_pago not in ('Efectivo', 'Tarjeta', 'Transferencia'):
            metodo_pago = 'Efectivo'
        if not carrito:
            return jsonify({'success': False, 'message': 'El carrito está vacío.'}), 400

        db = get_db()
        total_srv = 0.0

        # Verificar stock y calcular total servidor (no confiar en cliente)
        for item in carrito:
            row = db.execute(
                "SELECT stock_actual, nombre_producto, precio_venta FROM productos WHERE id_producto=?",
                (item['id'],)
            ).fetchone()
            if not row:
                raise ValueError(f"Producto ID {item['id']} no encontrado.")
            if row['stock_actual'] < int(item['cantidad']):
                raise ValueError(
                    f"Stock insuficiente para «{row['nombre_producto']}». "
                    f"Disponible: {row['stock_actual']}."
                )
            total_srv += float(row['precio_venta']) * int(item['cantidad'])

        descuento_pct = min(max(descuento_pct, 0.0), 100.0)
        desc_monto  = round(total_srv * (descuento_pct / 100.0), 2)
        total_final = round(total_srv - desc_monto, 2)
        # Los precios incluyen IVA: desglosar subtotal (base imponible) e IVA
        subtotal_base = round(total_final / (1 + IVA_PCT / 100.0), 2)
        iva_monto     = round(total_final - subtotal_base, 2)

        # La BD heredada tiene id_local NOT NULL sin default: incluirlo si existe
        vcols = [c['name'] for c in db.execute("PRAGMA table_info(ventas)").fetchall()]
        extra_col = ', id_local, ' if 'id_local' in vcols else ', '
        extra_val = ', 1, '        if 'id_local' in vcols else ', '
        cur = db.execute(
            f"""INSERT INTO ventas
               (cedula_cliente, id_empleado, id_sucursal{extra_col}fecha_venta,
                subtotal, iva, descuento, total, estado, metodo_pago, banco)
               VALUES (?, ?, 1{extra_val}CURRENT_TIMESTAMP, ?, ?, ?, ?, 'completada', ?, ?)""",
            (cedula, g.user['id_usuario'], subtotal_base, iva_monto,
             desc_monto, total_final, metodo_pago, banco)
        )
        id_venta = cur.lastrowid

        # Insertar detalles y descontar stock
        for item in carrito:
            row = db.execute(
                "SELECT precio_venta FROM productos WHERE id_producto=?", (item['id'],)
            ).fetchone()
            cant   = int(item['cantidad'])
            precio = float(row['precio_venta'])
            sub    = round(precio * cant, 2)
            db.execute(
                "INSERT INTO detalle_venta (id_venta,id_producto,cantidad,precio_unitario,subtotal) VALUES (?,?,?,?,?)",
                (id_venta, item['id'], cant, precio, sub)
            )
            # ── STOCK SE ACTUALIZA AUTOMÁTICAMENTE ──
            db.execute(
                "UPDATE productos SET stock_actual=stock_actual-? WHERE id_producto=?",
                (cant, item['id'])
            )

        db.commit()

        # Obtener nombre del cliente para el recibo
        cliente    = db.execute(
            "SELECT nombres,apellidos FROM clientes WHERE cedula=?", (cedula,)
        ).fetchone()
        nombre_cli = f"{cliente['nombres']} {cliente['apellidos']}" if cliente else 'Consumidor Final'

        return jsonify({
            'success': True, 'id_venta': id_venta, 'total': total_final,
            'subtotal': subtotal_base, 'iva': iva_monto, 'iva_pct': IVA_PCT,
            'descuento': desc_monto,
            'nombre_cliente': nombre_cli, 'cedula_cliente': cedula,
            'metodo_pago': metodo_pago, 'banco': banco or '',
            'empleado': g.user['nombre'],
            'fecha': datetime.now().strftime('%d/%m/%Y %H:%M')
        })

    except ValueError as e:
        if db:
            try: db.rollback()
            except Exception: pass
        return jsonify({'success': False, 'message': str(e)}), 400
    except sqlite3.Error:
        if db:
            try: db.rollback()
            except Exception: pass
        app.logger.exception('Error de BD al finalizar venta')
        return jsonify({'success': False, 'message': 'Error de base de datos. Contacta al administrador.'}), 500
    except Exception:
        if db:
            try: db.rollback()
            except Exception: pass
        app.logger.exception('Error inesperado al finalizar venta')
        return jsonify({'success': False, 'message': 'Error inesperado. Contacta al administrador.'}), 500
    finally:
        if db:
            try: db.close()
            except Exception: pass


# ── HISTORIAL VENTAS ────────────────────────────────────────────────────────
@app.route('/historial_ventas')
@role_required('Administrador', 'Vendedor')
def ver_historial_ventas():
    ventas = []
    try:
        db = get_db()
        ventas = db.execute(
            "SELECT v.id_venta,v.fecha_venta,v.total,v.estado,v.metodo_pago,v.banco,COALESCE(c.nombres||' '||c.apellidos,'Público General') nombre_cliente,u.nombre nombre_empleado FROM ventas v LEFT JOIN clientes c ON v.cedula_cliente=c.cedula JOIN usuario u ON v.id_empleado=u.id_usuario ORDER BY v.fecha_venta DESC LIMIT 200"
        ).fetchall()
        db.close()
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return render_template('ventas/historial.html', ventas=ventas, user_role=g.user.get('role'))


@app.route('/ventas/detalle/<int:id_venta>')
@role_required('Administrador', 'Vendedor')
def ver_detalle_venta(id_venta):
    try:
        db = get_db()
        venta = db.execute(
            "SELECT v.*,u.nombre nombre_empleado,COALESCE(c.nombres||' '||c.apellidos,'Público General') nombre_cliente FROM ventas v JOIN usuario u ON v.id_empleado=u.id_usuario LEFT JOIN clientes c ON v.cedula_cliente=c.cedula WHERE v.id_venta=?",
            (id_venta,)
        ).fetchone()
        if not venta:
            flash('Venta no encontrada.', 'danger')
            return redirect(url_for('ver_historial_ventas'))
        detalles = db.execute(
            "SELECT dv.*,p.nombre_producto,p.codigo_producto FROM detalle_venta dv JOIN productos p ON dv.id_producto=p.id_producto WHERE dv.id_venta=?",
            (id_venta,)
        ).fetchall()
        db.close()
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
        return redirect(url_for('ver_historial_ventas'))
    return render_template('ventas/detalle.html', venta=venta, detalles=detalles, user_role=g.user.get('role'))


@app.route('/ventas/anular/<int:id_venta>', methods=['POST'])
@admin_required
def anular_venta(id_venta):
    db = None
    try:
        db = get_db()
        venta = db.execute("SELECT id_venta, estado FROM ventas WHERE id_venta=?", (id_venta,)).fetchone()
        if not venta:
            flash('Venta no encontrada.', 'danger')
            return redirect(url_for('ver_historial_ventas'))
        if venta['estado'] != 'completada':
            flash('Solo se pueden anular ventas completadas.', 'warning')
            return redirect(url_for('ver_detalle_venta', id_venta=id_venta))
        # Reponer stock de cada producto vendido
        detalles = db.execute(
            "SELECT id_producto, cantidad FROM detalle_venta WHERE id_venta=?", (id_venta,)
        ).fetchall()
        for d in detalles:
            db.execute("UPDATE productos SET stock_actual=stock_actual+? WHERE id_producto=?",
                       (d['cantidad'], d['id_producto']))
        db.execute("UPDATE ventas SET estado='anulada' WHERE id_venta=?", (id_venta,))
        db.commit()
        flash(f'Venta #{id_venta} anulada y stock repuesto.', 'info')
    except sqlite3.Error:
        if db:
            try: db.rollback()
            except Exception: pass
        app.logger.exception('Error al anular venta')
        flash('Error al anular la venta.', 'danger')
    finally:
        if db:
            try: db.close()
            except Exception: pass
    return redirect(url_for('ver_detalle_venta', id_venta=id_venta))


# ── EGRESOS ─────────────────────────────────────────────────────────────────
@app.route('/egresos')
@role_required('Administrador', 'Vendedor')
def listar_egresos():
    q   = request.args.get('q', '').strip()
    mes = request.args.get('mes', '')
    try:
        db = get_db()
        sql = "SELECT e.*,p.nombre_empresa,u.nombre nombre_empleado FROM egresos e LEFT JOIN proveedores p ON e.id_proveedor=p.id_proveedor LEFT JOIN usuario u ON e.id_empleado=u.id_usuario WHERE 1=1"
        params = []
        if q:
            sql += " AND (e.descripcion LIKE ? OR e.categoria LIKE ?)"
            params += [f'%{q}%', f'%{q}%']
        if mes:
            sql += " AND strftime('%Y-%m',e.fecha)=?"
            params += [mes]
        sql += " ORDER BY e.fecha DESC LIMIT 200"
        egresos  = db.execute(sql, params).fetchall()
        resumen  = db.execute("SELECT COALESCE(SUM(monto),0) s, COUNT(*) c FROM egresos WHERE DATE(fecha)=DATE('now')").fetchone()
        prov     = db.execute("SELECT * FROM proveedores ORDER BY nombre_empresa").fetchall()
        db.close()
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
        egresos = []
        resumen = {'s': 0, 'c': 0}
        prov = []
    return render_template('egresos/lista.html', egresos=egresos, resumen=resumen,
                           proveedores=prov, categorias=CATEGORIAS_EGRESO,
                           bancos=BANCOS_EC, query=q, mes=mes,
                           user_role=g.user.get('role'))


@app.route('/egresos/agregar', methods=['POST'])
@role_required('Administrador', 'Vendedor')
def agregar_egreso():
    f = request.form
    if not f.get('descripcion') or not f.get('monto') or not f.get('categoria'):
        flash('Descripción, Categoría y Monto son obligatorios.', 'danger')
        return redirect(url_for('listar_egresos'))
    try:
        db = get_db()
        db.execute(
            "INSERT INTO egresos (categoria,descripcion,monto,metodo_pago,banco,id_proveedor,id_empleado) VALUES (?,?,?,?,?,?,?)",
            (f['categoria'], f['descripcion'], float(f['monto']),
             f.get('metodo_pago','Efectivo'), f.get('banco','') or None,
             f.get('id_proveedor') or None, g.user['id_usuario'])
        )
        db.commit()
        db.close()
        flash('Egreso registrado.', 'success')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('listar_egresos'))


@app.route('/egresos/eliminar/<int:id_egreso>', methods=['POST'])
@admin_required
def eliminar_egreso(id_egreso):
    try:
        db = get_db()
        db.execute("DELETE FROM egresos WHERE id_egreso=?", (id_egreso,))
        db.commit()
        db.close()
        flash('Egreso eliminado.', 'info')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('listar_egresos'))


# ── PRODUCTOS ───────────────────────────────────────────────────────────────
@app.route('/productos')
@role_required('Administrador', 'Vendedor')
def listar_productos():
    user_role = g.user.get('role')
    q      = request.args.get('q', '').strip()
    cat_id = request.args.get('cat', '').strip()
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    per_page = 20
    offset   = (page - 1) * per_page
    try:
        db = get_db()
        base = "FROM productos p LEFT JOIN proveedores pv ON p.id_proveedor=pv.id_proveedor LEFT JOIN categorias c ON p.id_categoria=c.id_categoria"
        conds, params = [], ()
        if q:
            conds.append("(p.nombre_producto LIKE ? OR p.codigo_producto LIKE ?)")
            params += (f'%{q}%', f'%{q}%')
        if cat_id:
            conds.append("p.id_categoria = ?")
            params += (cat_id,)
        where = ("WHERE " + " AND ".join(conds)) if conds else "" 
        total    = db.execute(f"SELECT COUNT(*) {base} {where}", params).fetchone()[0]
        productos = db.execute(
            f"SELECT p.*,pv.nombre_empresa nombre_proveedor,c.nombre_categoria {base} {where} ORDER BY p.nombre_producto LIMIT ? OFFSET ?",
            (*params, per_page, offset)
        ).fetchall()
        all_prods = db.execute("SELECT codigo_producto,nombre_producto,precio_venta,medida FROM productos ORDER BY nombre_producto").fetchall() if user_role=='Administrador' else []
        cat_nombre = ''
        if cat_id:
            cat_row = db.execute("SELECT nombre_categoria FROM categorias WHERE id_categoria=?", (cat_id,)).fetchone()
            if cat_row: cat_nombre = cat_row['nombre_categoria']
        db.close()
        total_pages = max(1, (total + per_page - 1) // per_page)
        import json
        all_prods_json = json.dumps([
            {'code': r['codigo_producto'], 'name': r['nombre_producto'],
             'price': float(r['precio_venta']), 'medida': r['medida'] or ''}
            for r in all_prods
        ])
        return render_template('productos/lista.html',
                               productos=productos, query=q, page=page,
                               total_pages=total_pages, total_productos=total,
                               user_role=user_role, all_productos=all_prods,
                               all_productos_json=all_prods_json,
                               cat_id=cat_id, cat_nombre=cat_nombre)
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/productos/agregar', methods=['GET', 'POST'])
@admin_required
def agregar_producto():
    db = get_db()
    cats  = db.execute("SELECT DISTINCT id_categoria,nombre_categoria FROM categorias ORDER BY nombre_categoria").fetchall()
    provs = db.execute("SELECT * FROM proveedores ORDER BY nombre_empresa").fetchall()
    db.close()
    if request.method == 'POST':
        f = request.form
        if not f.get('codigo_producto','').strip() or not f.get('nombre_producto','').strip() or not f.get('id_categoria','').strip():
            flash('Código, Nombre y Categoría son obligatorios.', 'danger')
            return render_template('productos/agregar.html', categorias=cats, proveedores=provs, form_data=f)
        codigo = f['codigo_producto'].strip().upper()
        pc = float(f.get('precio_compra', 0) or 0)
        pv_raw = f.get('precio_venta', '').strip()
        pv = float(pv_raw) if pv_raw else round(pc * 1.60, 2)
        try:
            db = get_db()
            if db.execute("SELECT 1 FROM productos WHERE codigo_producto=?", (codigo,)).fetchone():
                flash(f'El código «{codigo}» ya existe.', 'danger')
                return render_template('productos/agregar.html', categorias=cats, proveedores=provs, form_data=f)
            db.execute(
                "INSERT INTO productos (codigo_producto,nombre_producto,descripcion,material,tipo_rosca,medida,unidad_medida,precio_compra,precio_venta,stock_actual,stock_minimo,id_proveedor,id_categoria) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (codigo, f['nombre_producto'], f.get('descripcion',''),
                 f.get('material','N/A') or 'N/A', f.get('tipo_rosca','N/A') or 'N/A',
                 f.get('medida','N/A') or 'N/A', f.get('unidad_medida','unidad') or 'unidad',
                 pc, pv, int(f.get('stock_actual',0) or 0), int(f.get('stock_minimo',10) or 10),
                 f.get('id_proveedor') or None, f['id_categoria'])
            )
            db.commit()
            flash(f'Producto «{f["nombre_producto"]}» agregado.', 'success')
            return redirect(url_for('listar_productos'))
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
            return render_template('productos/agregar.html', categorias=cats, proveedores=provs, form_data=f)
        finally:
            db.close()
    return render_template('productos/agregar.html', categorias=cats, proveedores=provs)


@app.route('/productos/editar/<int:id_producto>', methods=['GET', 'POST'])
@admin_required
def editar_producto(id_producto):
    db   = get_db()
    row  = db.execute("SELECT * FROM productos WHERE id_producto=?", (id_producto,)).fetchone()
    cats = db.execute("SELECT DISTINCT id_categoria,nombre_categoria FROM categorias ORDER BY nombre_categoria").fetchall()
    provs = db.execute("SELECT * FROM proveedores ORDER BY nombre_empresa").fetchall()
    db.close()
    prod = dict(row) if row else None
    cats  = [dict(r) for r in cats]
    provs = [dict(r) for r in provs]
    if not prod:
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('listar_productos'))
    if request.method == 'POST':
        f = request.form
        codigo = f['codigo_producto'].strip().upper()
        try:
            db = get_db()
            if db.execute("SELECT 1 FROM productos WHERE codigo_producto=? AND id_producto!=?", (codigo, id_producto)).fetchone():
                flash(f'El código «{codigo}» ya existe.', 'danger')
            else:
                pc   = float(f.get('precio_compra', 0) or 0)
                pv_r = f.get('precio_venta', '').strip()
                pv   = float(pv_r) if pv_r else round(pc * 1.60, 2)
                db.execute(
                    "UPDATE productos SET codigo_producto=?,nombre_producto=?,descripcion=?,material=?,tipo_rosca=?,medida=?,unidad_medida=?,precio_compra=?,precio_venta=?,stock_actual=?,stock_minimo=?,id_proveedor=?,id_categoria=?,fecha_actualizacion=CURRENT_TIMESTAMP WHERE id_producto=?",
                    (codigo, f['nombre_producto'], f.get('descripcion',''),
                     f.get('material','N/A') or 'N/A', f.get('tipo_rosca','N/A') or 'N/A',
                     f.get('medida','N/A') or 'N/A', f.get('unidad_medida','unidad') or 'unidad',
                     pc, pv, int(f.get('stock_actual',0) or 0), int(f.get('stock_minimo',10) or 10),
                     f.get('id_proveedor') or None, f['id_categoria'], id_producto)
                )
                db.commit()
                flash('Producto actualizado.', 'success')
                return redirect(url_for('listar_productos'))
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
        finally:
            db.close()
    return render_template('productos/editar.html', producto=prod, categorias=cats, proveedores=provs,
                           form_data=request.form if request.method == 'POST' else None)


@app.route('/productos/eliminar/<int:id_producto>', methods=['POST'])
@admin_required
def eliminar_producto(id_producto):
    try:
        db = get_db()
        db.execute("DELETE FROM productos WHERE id_producto=?", (id_producto,))
        db.commit()
        db.close()
        flash('Producto eliminado.', 'info')
    except sqlite3.IntegrityError:
        flash('No se puede eliminar: tiene ventas asociadas.', 'danger')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('listar_productos'))


# ── APIs PRODUCTO ───────────────────────────────────────────────────────────
@app.route('/api/next_code')
@admin_required
def api_next_code():
    id_cat = request.args.get('id_categoria', '').strip()
    if not id_cat:
        return jsonify({'codigo': 'OTR-001', 'prefijo': 'OTR'})
    db  = get_db()
    cat = db.execute("SELECT nombre_categoria FROM categorias WHERE id_categoria=?", (id_cat,)).fetchone()
    if not cat:
        db.close()
        return jsonify({'codigo': 'OTR-001', 'prefijo': 'OTR'})
    pref = _prefijo_cat(cat['nombre_categoria'])
    rows = db.execute("SELECT codigo_producto FROM productos WHERE codigo_producto LIKE ? ORDER BY codigo_producto", (f'{pref}-%',)).fetchall()
    db.close()
    max_n = 0
    for r in rows:
        parts = r['codigo_producto'].split('-')
        if len(parts) >= 2 and parts[-1].isdigit():
            max_n = max(max_n, int(parts[-1]))
    return jsonify({'codigo': f'{pref}-{str(max_n+1).zfill(3)}', 'prefijo': pref})


@app.route('/api/agregar_categoria', methods=['POST'])
@admin_required
def api_agregar_categoria():
    data   = request.get_json(silent=True) or {}
    nombre = data.get('nombre', '').strip()
    if not nombre:
        return jsonify({'success': False, 'message': 'Nombre requerido.'}), 400
    try:
        db = get_db()
        db.execute("INSERT INTO categorias (nombre_categoria) VALUES (?)", (nombre,))
        db.commit()
        row = db.execute("SELECT id_categoria FROM categorias WHERE nombre_categoria=?", (nombre,)).fetchone()
        db.close()
        return jsonify({'success': True, 'id_categoria': row['id_categoria'], 'nombre': nombre, 'prefijo': _prefijo_cat(nombre)})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': f'La categoría «{nombre}» ya existe.'}), 409
    except sqlite3.Error as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ── PROVEEDORES ─────────────────────────────────────────────────────────────
@app.route('/proveedores')
@role_required('Administrador', 'Vendedor')
def listar_proveedores():
    try:
        page = max(1, int(request.args.get('page', 1)))
    except ValueError:
        page = 1
    per_page = 10
    offset   = (page - 1) * per_page
    db       = get_db()
    total    = db.execute("SELECT COUNT(*) FROM proveedores").fetchone()[0]
    provs    = db.execute("SELECT * FROM proveedores ORDER BY nombre_empresa LIMIT ? OFFSET ?", (per_page, offset)).fetchall()
    db.close()
    return render_template('proveedores/lista.html', proveedores=provs, page=page,
                           total_pages=max(1,(total+per_page-1)//per_page),
                           total_proveedores=total, user_role=g.user.get('role'))


@app.route('/proveedores/agregar', methods=['GET', 'POST'])
@admin_required
def agregar_proveedor():
    if request.method == 'POST':
        f = request.form
        if not all([f.get('ruc'), f.get('nombre_empresa'), f.get('contacto'), f.get('telefono')]):
            flash('RUC, Nombre, Contacto y Teléfono son obligatorios.', 'danger')
            return render_template('proveedores/agregar.html', form_data=f)
        try:
            db = get_db()
            db.execute("INSERT INTO proveedores (ruc,nombre_empresa,contacto,telefono,email,direccion) VALUES (?,?,?,?,?,?)",
                       (f['ruc'],f['nombre_empresa'],f['contacto'],f['telefono'],f.get('email',''),f.get('direccion','')))
            db.commit()
            flash('Proveedor agregado.', 'success')
            return redirect(url_for('listar_proveedores'))
        except sqlite3.IntegrityError:
            flash(f'El RUC «{f["ruc"]}» ya existe.', 'danger')
            return render_template('proveedores/agregar.html', form_data=f)
        finally:
            db.close()
    return render_template('proveedores/agregar.html')


@app.route('/proveedores/editar/<int:id_proveedor>', methods=['GET', 'POST'])
@admin_required
def editar_proveedor(id_proveedor):
    db   = get_db()
    row = db.execute("SELECT * FROM proveedores WHERE id_proveedor=?", (id_proveedor,)).fetchone()
    db.close()
    prov = dict(row) if row else None
    if not prov:
        flash('No encontrado.', 'danger')
        return redirect(url_for('listar_proveedores'))
    if request.method == 'POST':
        f = request.form
        try:
            db = get_db()
            if db.execute("SELECT 1 FROM proveedores WHERE ruc=? AND id_proveedor!=?", (f['ruc'], id_proveedor)).fetchone():
                flash('RUC duplicado.', 'danger')
            else:
                db.execute("UPDATE proveedores SET ruc=?,nombre_empresa=?,contacto=?,telefono=?,email=?,direccion=? WHERE id_proveedor=?",
                           (f['ruc'],f['nombre_empresa'],f['contacto'],f['telefono'],f.get('email',''),f.get('direccion',''),id_proveedor))
                db.commit()
                flash('Proveedor actualizado.', 'success')
                return redirect(url_for('listar_proveedores'))
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
        finally:
            db.close()
    return render_template('proveedores/editar.html', proveedor=prov, form_data=request.form if request.method == 'POST' else None)


@app.route('/proveedores/eliminar/<int:id_proveedor>', methods=['POST'])
@admin_required
def eliminar_proveedor(id_proveedor):
    try:
        db = get_db()
        db.execute("DELETE FROM proveedores WHERE id_proveedor=?", (id_proveedor,))
        db.commit()
        db.close()
        flash('Proveedor eliminado.', 'info')
    except sqlite3.IntegrityError:
        flash('No se puede eliminar: tiene productos asociados.', 'danger')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('listar_proveedores'))


# ── CLIENTES ────────────────────────────────────────────────────────────────
@app.route('/clientes')
@role_required('Administrador', 'Vendedor')
def listar_clientes():
    q = request.args.get('q', '').strip()
    db = get_db()
    if q:
        term = f'%{q}%'
        clts = db.execute("SELECT * FROM clientes WHERE cedula LIKE ? OR nombres LIKE ? OR apellidos LIKE ? ORDER BY apellidos", (term,term,term)).fetchall()
    else:
        clts = db.execute("SELECT * FROM clientes ORDER BY apellidos").fetchall()
    db.close()
    return render_template('clientes/lista.html', clientes=clts, query=q, user_role=g.user.get('role'))


@app.route('/clientes/agregar', methods=['GET', 'POST'])
@role_required('Administrador', 'Vendedor')
def agregar_cliente():
    if request.method == 'POST':
        f = request.form
        if not all([f.get('cedula'), f.get('nombres'), f.get('apellidos')]):
            flash('Cédula, Nombres y Apellidos son obligatorios.', 'danger')
            return render_template('clientes/agregar.html', form_data=f)
        try:
            db = get_db()
            cols = [c['name'] for c in db.execute("PRAGMA table_info(clientes)").fetchall()]
            if 'tipo' in cols:
                db.execute("INSERT INTO clientes (cedula,nombres,apellidos,telefono,email,direccion,tipo) VALUES (?,?,?,?,?,?,?)",
                           (f['cedula'],f['nombres'],f['apellidos'],f.get('telefono',''),f.get('email',''),f.get('direccion',''),f.get('tipo','minorista')))
            else:
                db.execute("INSERT INTO clientes (cedula,nombres,apellidos,telefono,email,direccion) VALUES (?,?,?,?,?,?)",
                           (f['cedula'],f['nombres'],f['apellidos'],f.get('telefono',''),f.get('email',''),f.get('direccion','')))
            db.commit()
            flash('Cliente registrado.', 'success')
            return redirect(url_for('listar_clientes'))
        except sqlite3.IntegrityError:
            flash(f'La cédula «{f["cedula"]}» ya existe.', 'danger')
            return render_template('clientes/agregar.html', form_data=f)
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
            return render_template('clientes/agregar.html', form_data=f)
        finally:
            db.close()
    return render_template('clientes/agregar.html')


@app.route('/clientes/editar/<cedula>', methods=['GET', 'POST'])
@role_required('Administrador', 'Vendedor')
def editar_cliente(cedula):
    db   = get_db()
    row = db.execute("SELECT * FROM clientes WHERE cedula=?", (cedula,)).fetchone()
    db.close()
    clt = dict(row) if row else None
    if not clt:
        flash('No encontrado.', 'danger')
        return redirect(url_for('listar_clientes'))
    if request.method == 'POST':
        f = request.form
        try:
            db = get_db()
            cols = [c['name'] for c in db.execute("PRAGMA table_info(clientes)").fetchall()]
            if 'tipo' in cols:
                db.execute("UPDATE clientes SET nombres=?,apellidos=?,telefono=?,email=?,direccion=?,tipo=? WHERE cedula=?",
                           (f['nombres'],f['apellidos'],f.get('telefono',''),f.get('email',''),f.get('direccion',''),f.get('tipo','minorista'),cedula))
            else:
                db.execute("UPDATE clientes SET nombres=?,apellidos=?,telefono=?,email=?,direccion=? WHERE cedula=?",
                           (f['nombres'],f['apellidos'],f.get('telefono',''),f.get('email',''),f.get('direccion',''),cedula))
            db.commit()
            flash('Cliente actualizado.', 'success')
            return redirect(url_for('listar_clientes'))
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
        finally:
            db.close()
    return render_template('clientes/editar.html', cliente=clt, form_data=request.form if request.method == 'POST' else None)


@app.route('/clientes/eliminar/<cedula>', methods=['POST'])
@admin_required
def eliminar_cliente(cedula):
    try:
        db = get_db()
        n_ventas = db.execute("SELECT COUNT(*) FROM ventas WHERE cedula_cliente=?", (cedula,)).fetchone()[0]
        if n_ventas:
            db.close()
            flash(f'No se puede eliminar: el cliente tiene {n_ventas} venta(s) registrada(s).', 'danger')
            return redirect(url_for('listar_clientes'))
        db.execute("DELETE FROM clientes WHERE cedula=?", (cedula,))
        db.commit()
        db.close()
        flash('Cliente eliminado.', 'info')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('listar_clientes'))


# ── USUARIOS ────────────────────────────────────────────────────────────────
@app.route('/usuarios')
@admin_required
def listar_usuarios():
    db   = get_db()
    usu  = db.execute("SELECT id_usuario,email,nombre,role FROM usuario ORDER BY nombre").fetchall()
    db.close()
    return render_template('usuarios/lista.html', usuarios=usu, user_role=g.user.get('role'))


@app.route('/usuarios/agregar', methods=['GET', 'POST'])
@admin_required
def agregar_usuario():
    roles = ['Administrador', 'Vendedor']
    if request.method == 'POST':
        f = request.form
        if not all([f.get('email'), f.get('password'), f.get('nombre'), f.get('role')]):
            flash('Todos los campos son obligatorios.', 'danger')
            return render_template('usuarios/agregar.html', roles=roles, form_data=f)
        try:
            db = get_db()
            if db.execute("SELECT 1 FROM usuario WHERE email=?", (f['email'],)).fetchone():
                flash('Email ya registrado.', 'warning')
                return render_template('usuarios/agregar.html', roles=roles, form_data=f)
            cur = db.execute("INSERT INTO usuario (email,password,nombre,role) VALUES (?,?,?,?)",
                             (f['email'].strip().lower(), hash_password(f['password']), f['nombre'], f['role']))
            nuevo_id = cur.lastrowid
            # La BD heredada exige ventas.id_empleado → empleados: crear fila espejo
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='empleados'").fetchone():
                if not db.execute("SELECT 1 FROM empleados WHERE id_empleado=?", (nuevo_id,)).fetchone():
                    partes = f['nombre'].split(' ', 1)
                    db.execute("""INSERT INTO empleados
                                  (id_empleado, cedula, nombres, apellidos, cargo,
                                   telefono, email, id_local, fecha_contratacion, activo)
                                  VALUES (?, ?, ?, ?, 'Vendedor', 'N/A', ?, 1, DATE('now'), 1)""",
                               (nuevo_id, f'USR-{nuevo_id}', partes[0],
                                partes[1] if len(partes) > 1 else 'N/A', f['email'].strip().lower()))
            db.commit()
            flash(f'Usuario «{f["nombre"]}» creado.', 'success')
            return redirect(url_for('listar_usuarios'))
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
            return render_template('usuarios/agregar.html', roles=roles, form_data=f)
        finally:
            db.close()
    return render_template('usuarios/agregar.html', roles=roles)


@app.route('/usuarios/cambiar_password/<int:id_usuario>', methods=['POST'])
@admin_required
def cambiar_password(id_usuario):
    nueva = request.form.get('nueva_password', '').strip()
    if len(nueva) < 6:
        flash('Mínimo 6 caracteres.', 'danger')
        return redirect(url_for('listar_usuarios'))
    db = get_db()
    db.execute("UPDATE usuario SET password=? WHERE id_usuario=?", (hash_password(nueva), id_usuario))
    db.commit()
    db.close()
    flash('Contraseña actualizada.', 'success')
    return redirect(url_for('listar_usuarios'))


@app.route('/usuarios/eliminar/<int:id_usuario>', methods=['POST'])
@admin_required
def eliminar_usuario(id_usuario):
    if g.user['id_usuario'] == id_usuario:
        flash('No puedes eliminarte a ti mismo.', 'danger')
        return redirect(url_for('listar_usuarios'))
    try:
        db = get_db()
        db.execute("DELETE FROM usuario WHERE id_usuario=?", (id_usuario,))
        db.commit()
        flash('Usuario eliminado.', 'info')
    except sqlite3.IntegrityError:
        flash('No se puede eliminar: el usuario tiene ventas registradas.', 'danger')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    finally:
        try: db.close()
        except Exception: pass
    return redirect(url_for('listar_usuarios'))


# ── REPORTES ────────────────────────────────────────────────────────────────
@app.route('/reportes')
@admin_required
def generar_reportes():
    periodo     = request.args.get('periodo', 'mes')
    anio_sel    = request.args.get('anio', str(datetime.now().year))
    top_periodo = request.args.get('top_periodo', 'mes')
    vista       = request.args.get('vista', 'general')   # general | ingresos | egresos | combinado

    def _desde(p):
        hoy = datetime.now()
        if p == 'dia':      return hoy.strftime('%Y-%m-%d')
        if p == 'semana':   return (hoy - timedelta(days=7)).strftime('%Y-%m-%d')
        if p == 'mes':      return hoy.strftime('%Y-%m-01')
        if p == 'trimestre':
            mes = ((hoy.month-1)//3)*3+1
            return hoy.replace(month=mes, day=1).strftime('%Y-%m-%d')
        if p == 'semestre':
            return hoy.replace(month=1 if hoy.month<=6 else 7, day=1).strftime('%Y-%m-%d')
        return f'{hoy.year}-01-01'

    try:
        db  = get_db()
        dia = _desde(periodo)

        # ── ANIOS disponibles
        anios = [r['a'] for r in db.execute(
            "SELECT DISTINCT strftime('%Y',fecha_venta) a FROM ventas ORDER BY a DESC"
        ).fetchall() if r['a']]

        # ── VENTAS por día
        ventas_dia = [dict(r) for r in db.execute(
            """SELECT DATE(fecha_venta) dia, COUNT(*) cantidad,
                      COALESCE(SUM(total),0) total
               FROM ventas WHERE DATE(fecha_venta)>=? AND estado='completada'
               GROUP BY dia ORDER BY dia""", (dia,)
        ).fetchall()]

        # ── EGRESOS por día (mismo período)
        egresos_dia = [dict(r) for r in db.execute(
            """SELECT DATE(fecha) dia, COUNT(*) cantidad,
                      COALESCE(SUM(monto),0) total, categoria
               FROM egresos WHERE DATE(fecha)>=?
               GROUP BY dia ORDER BY dia""", (dia,)
        ).fetchall()]

        # ── EGRESOS por categoría (período)
        egresos_cat = [dict(r) for r in db.execute(
            """SELECT categoria, COUNT(*) num,
                      COALESCE(SUM(monto),0) total
               FROM egresos WHERE DATE(fecha)>=?
               GROUP BY categoria ORDER BY total DESC""", (dia,)
        ).fetchall()]

        # ── EGRESOS del período completo
        egresos_periodo = dict(db.execute(
            """SELECT COALESCE(SUM(monto),0) total, COUNT(*) num
               FROM egresos WHERE DATE(fecha)>=?""", (dia,)
        ).fetchone())

        # ── CIERRE HOY (ingresos)
        cierre = dict(db.execute(
            """SELECT COUNT(*) num_ventas,
                      COALESCE(SUM(total),0) total_dia,
                      SUM(CASE WHEN metodo_pago='Efectivo'      THEN total ELSE 0 END) efectivo,
                      SUM(CASE WHEN metodo_pago='Transferencia' THEN total ELSE 0 END) transferencia,
                      SUM(CASE WHEN metodo_pago='Tarjeta'       THEN total ELSE 0 END) tarjeta
               FROM ventas WHERE DATE(fecha_venta)=DATE('now') AND estado='completada'"""
        ).fetchone())

        # ── EGRESOS HOY
        egresos_hoy = dict(db.execute(
            """SELECT COALESCE(SUM(monto),0) total, COUNT(*) num
               FROM egresos WHERE DATE(fecha)=DATE('now')"""
        ).fetchone())

        # ── EGRESOS HOY por categoría
        egresos_hoy_cat = [dict(r) for r in db.execute(
            """SELECT categoria, descripcion, monto, metodo_pago, fecha
               FROM egresos WHERE DATE(fecha)=DATE('now')
               ORDER BY fecha DESC"""
        ).fetchall()]

        # ── TOP PRODUCTOS
        top_prods = [dict(r) for r in db.execute(
            """SELECT p.nombre_producto, SUM(dv.cantidad) total_vendido,
                      SUM(dv.subtotal) ingresos
               FROM detalle_venta dv
               JOIN productos p ON dv.id_producto=p.id_producto
               JOIN ventas v ON dv.id_venta=v.id_venta
               WHERE DATE(v.fecha_venta)>=? AND v.estado='completada'
               GROUP BY dv.id_producto ORDER BY total_vendido DESC LIMIT 10""",
            (_desde(top_periodo),)
        ).fetchall()]

        # ── RESUMEN AÑO
        res_anio = dict(db.execute(
            """SELECT COUNT(*) total_ventas,
                      COALESCE(SUM(total),0) ingresos_totales,
                      COALESCE(AVG(total),0) ticket_promedio,
                      SUM(CASE WHEN metodo_pago='Efectivo'      THEN total ELSE 0 END) efectivo,
                      SUM(CASE WHEN metodo_pago='Transferencia' THEN total ELSE 0 END) transferencia,
                      SUM(CASE WHEN metodo_pago='Tarjeta'       THEN total ELSE 0 END) tarjeta
               FROM ventas WHERE strftime('%Y',fecha_venta)=? AND estado='completada'""",
            (anio_sel,)
        ).fetchone())

        # ── EGRESOS AÑO
        egresos_anio = dict(db.execute(
            """SELECT COALESCE(SUM(monto),0) total, COUNT(*) num
               FROM egresos WHERE strftime('%Y',fecha)=?""", (anio_sel,)
        ).fetchone())

        # ── UTILIDAD = ingresos - egresos (período)
        ingresos_periodo = sum(r['total'] for r in ventas_dia)
        utilidad_periodo = ingresos_periodo - egresos_periodo['total']

        # ── CATEGORÍAS HOY
        cats_hoy = [dict(r) for r in db.execute(
            """SELECT c.nombre_categoria, SUM(dv.cantidad) unidades, SUM(dv.subtotal) total
               FROM detalle_venta dv
               JOIN productos p ON dv.id_producto=p.id_producto
               JOIN categorias c ON p.id_categoria=c.id_categoria
               JOIN ventas v ON dv.id_venta=v.id_venta
               WHERE DATE(v.fecha_venta)=DATE('now') AND v.estado='completada'
               GROUP BY c.id_categoria ORDER BY total DESC"""
        ).fetchall()]

        # ── TABLA COMBINADA por día (ingresos vs egresos)
        fechas_set = set(r['dia'] for r in ventas_dia) | set(r['dia'] for r in egresos_dia)
        ventas_map  = {r['dia']: r for r in ventas_dia}
        egresos_map = {}
        for r in db.execute(
            "SELECT DATE(fecha) dia, COALESCE(SUM(monto),0) total FROM egresos WHERE DATE(fecha)>=? GROUP BY dia", (dia,)
        ).fetchall():
            egresos_map[r['dia']] = r['total']
        combinado = []
        for f in sorted(fechas_set):
            ing = ventas_map.get(f, {}).get('total', 0) or 0
            egr = egresos_map.get(f, 0) or 0
            combinado.append({'dia': f, 'ingresos': ing, 'egresos': egr, 'utilidad': ing - egr})

        db.close()

    except sqlite3.Error as e:
        flash(f'Error en reportes: {e}', 'danger')
        ventas_dia=egresos_dia=egresos_cat=top_prods=cats_hoy=anios=egresos_hoy_cat=combinado=[]
        cierre=egresos_hoy=egresos_periodo=egresos_anio={'total':0,'num':0,'num_ventas':0,'total_dia':0,'efectivo':0,'transferencia':0,'tarjeta':0}
        res_anio={'total_ventas':0,'ingresos_totales':0,'ticket_promedio':0,'efectivo':0,'transferencia':0,'tarjeta':0}
        ingresos_periodo=utilidad_periodo=0

    return render_template('reportes/index.html',
        ventas_dia=ventas_dia, egresos_dia=egresos_dia,
        egresos_cat=egresos_cat, egresos_hoy=egresos_hoy,
        egresos_hoy_cat=egresos_hoy_cat, egresos_periodo=egresos_periodo,
        egresos_anio=egresos_anio, combinado=combinado,
        top_productos=top_prods, resumen_anio=res_anio,
        cierre_hoy=cierre, ventas_cat_hoy=cats_hoy,
        ingresos_periodo=ingresos_periodo, utilidad_periodo=utilidad_periodo,
        anios=anios, anio_sel=anio_sel, periodo=periodo,
        top_periodo=top_periodo, vista=vista, now=datetime.now())


# ── CATEGORÍAS ──────────────────────────────────────────────────────────────
@app.route('/categorias')
@admin_required
def listar_categorias():
    try:
        db = get_db()
        cats = db.execute(
            "SELECT c.*,COUNT(p.id_producto) num_productos FROM categorias c LEFT JOIN productos p ON c.id_categoria=p.id_categoria GROUP BY c.id_categoria ORDER BY c.nombre_categoria"
        ).fetchall()
        db.close()
        cats = [dict(r) for r in cats]
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
        cats = []
    return render_template('categorias/vista.html', categorias=cats, user_role=g.user.get('role'))


@app.route('/categorias/eliminar/<int:id_categoria>', methods=['POST'])
@admin_required
def eliminar_categoria(id_categoria):
    try:
        db = get_db()
        db.execute("DELETE FROM categorias WHERE id_categoria=?", (id_categoria,))
        db.commit()
        db.close()
        flash('Categoría eliminada.', 'info')
    except sqlite3.IntegrityError:
        flash('No se puede eliminar: tiene productos asociados.', 'danger')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    return redirect(url_for('listar_categorias'))


# ── SUCURSALES ──────────────────────────────────────────────────────────────
@app.route('/sucursales')
@admin_required
def listar_sucursales():
    try:
        db = get_db()
        # Check if id_sucursal exists in productos before using it in subquery
        pcols = [c['name'] for c in db.execute("PRAGMA table_info(productos)").fetchall()]
        if 'id_sucursal' in pcols:
            suc = db.execute(
                "SELECT s.*,(SELECT COUNT(*) FROM productos WHERE id_sucursal=s.id_sucursal) num_productos FROM sucursales s ORDER BY es_matriz DESC,nombre"
            ).fetchall()
        else:
            # id_sucursal not yet in productos — show total count for all
            total_p = db.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
            raw = db.execute("SELECT * FROM sucursales ORDER BY es_matriz DESC,nombre").fetchall()
            # Attach product count as dict
            suc = []
            for r in raw:
                d = dict(r)
                d['num_productos'] = total_p if r['es_matriz'] else 0
                suc.append(d)
        db.close()
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
        suc = []
    return render_template('sucursales/lista.html', sucursales=suc)


@app.route('/sucursales/agregar', methods=['GET', 'POST'])
@admin_required
def agregar_sucursal():
    if request.method == 'POST':
        f = request.form
        if not f.get('nombre'):
            flash('El nombre es obligatorio.', 'danger')
            return render_template('sucursales/agregar.html', form_data=f)
        try:
            db = get_db()
            db.execute("INSERT INTO sucursales (nombre,direccion,telefono,ruc,activa) VALUES (?,?,?,?,1)",
                       (f['nombre'],f.get('direccion',''),f.get('telefono',''),f.get('ruc','')))
            db.commit()
            flash(f'Sucursal «{f["nombre"]}» creada.', 'success')
            return redirect(url_for('listar_sucursales'))
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
            return render_template('sucursales/agregar.html', form_data=f)
        finally:
            db.close()
    return render_template('sucursales/agregar.html')


@app.route('/sucursales/reporte/<int:id_sucursal>')
@admin_required
def reporte_sucursal(id_sucursal):
    try:
        db  = get_db()
        suc = db.execute("SELECT * FROM sucursales WHERE id_sucursal=?", (id_sucursal,)).fetchone()
        if not suc:
            flash('Sucursal no encontrada.', 'danger')
            db.close()
            return redirect(url_for('listar_sucursales'))

        # Check if id_sucursal column exists in productos/ventas/egresos
        pcols = [c['name'] for c in db.execute("PRAGMA table_info(productos)").fetchall()]
        vcols = [c['name'] for c in db.execute("PRAGMA table_info(ventas)").fetchall()]
        ecols = [c['name'] for c in db.execute("PRAGMA table_info(egresos)").fetchall()]
        has_suc_prod   = 'id_sucursal' in pcols
        has_suc_ventas = 'id_sucursal' in vcols
        has_suc_egres  = 'id_sucursal' in ecols

        if has_suc_prod:
            stats = db.execute(
                "SELECT COUNT(*) total_productos,COALESCE(SUM(stock_actual),0) total_stock,COALESCE(SUM(stock_actual*precio_venta),0) valor_inventario FROM productos WHERE id_sucursal=?",
                (id_sucursal,)
            ).fetchone()
            stock_bajo = db.execute(
                "SELECT nombre_producto,stock_actual,stock_minimo FROM productos WHERE id_sucursal=? AND stock_actual<stock_minimo ORDER BY (stock_actual-stock_minimo)",
                (id_sucursal,)
            ).fetchall()
        else:
            stats = db.execute(
                "SELECT COUNT(*) total_productos,COALESCE(SUM(stock_actual),0) total_stock,COALESCE(SUM(stock_actual*precio_venta),0) valor_inventario FROM productos"
            ).fetchone()
            stock_bajo = db.execute(
                "SELECT nombre_producto,stock_actual,stock_minimo FROM productos WHERE stock_actual<stock_minimo ORDER BY (stock_actual-stock_minimo)"
            ).fetchall()

        if has_suc_ventas:
            ventas_mes = db.execute(
                "SELECT COUNT(*) num,COALESCE(SUM(total),0) total FROM ventas WHERE id_sucursal=? AND strftime('%Y-%m',fecha_venta)=strftime('%Y-%m','now') AND estado='completada'",
                (id_sucursal,)
            ).fetchone()
        else:
            ventas_mes = db.execute(
                "SELECT COUNT(*) num,COALESCE(SUM(total),0) total FROM ventas WHERE strftime('%Y-%m',fecha_venta)=strftime('%Y-%m','now') AND estado='completada'"
            ).fetchone()

        if has_suc_egres:
            egresos_mes = db.execute(
                "SELECT COALESCE(SUM(monto),0) total FROM egresos WHERE id_sucursal=? AND strftime('%Y-%m',fecha)=strftime('%Y-%m','now')",
                (id_sucursal,)
            ).fetchone()
        else:
            egresos_mes = db.execute(
                "SELECT COALESCE(SUM(monto),0) total FROM egresos WHERE strftime('%Y-%m',fecha)=strftime('%Y-%m','now')"
            ).fetchone()

        db.close()
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
        try:
            db.close()
        except Exception:
            pass
        return redirect(url_for('listar_sucursales'))
    return render_template('sucursales/reporte.html', sucursal=suc, stats=stats,
                           ventas_mes=ventas_mes, egresos_mes=egresos_mes,
                           stock_bajo=stock_bajo, now=datetime.now())


@app.route('/sucursales/editar/<int:id_sucursal>', methods=['GET', 'POST'])
@admin_required
def editar_sucursal(id_sucursal):
    try:
        db = get_db()
        row = db.execute("SELECT * FROM sucursales WHERE id_sucursal=?", (id_sucursal,)).fetchone()
        db.close()
        suc = dict(row) if row else None
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
        return redirect(url_for('listar_sucursales'))

    if not suc:
        flash('Sucursal no encontrada.', 'danger')
        return redirect(url_for('listar_sucursales'))

    if request.method == 'POST':
        f = request.form
        if not f.get('nombre'):
            flash('El nombre es obligatorio.', 'danger')
            return render_template('sucursales/editar.html', sucursal=suc, form_data=f)
        try:
            db = get_db()
            db.execute(
                "UPDATE sucursales SET nombre=?,direccion=?,telefono=?,ruc=? WHERE id_sucursal=?",
                (f['nombre'], f.get('direccion',''), f.get('telefono',''), f.get('ruc',''), id_sucursal)
            )
            db.commit()
            flash(f'Sucursal «{f["nombre"]}» actualizada.', 'success')
            return redirect(url_for('listar_sucursales'))
        except sqlite3.Error as e:
            flash(f'Error: {e}', 'danger')
            return render_template('sucursales/editar.html', sucursal=suc, form_data=f)
        finally:
            try: db.close()
            except Exception: pass

    return render_template('sucursales/editar.html', sucursal=suc)


@app.route('/sucursales/eliminar/<int:id_sucursal>', methods=['POST'])
@admin_required
def eliminar_sucursal(id_sucursal):
    try:
        db = get_db()
        suc = db.execute("SELECT * FROM sucursales WHERE id_sucursal=?", (id_sucursal,)).fetchone()
        if not suc:
            flash('Sucursal no encontrada.', 'danger')
            db.close()
            return redirect(url_for('listar_sucursales'))
        if suc['es_matriz']:
            flash('No se puede eliminar la sucursal Matriz.', 'danger')
            db.close()
            return redirect(url_for('listar_sucursales'))
        db.execute("DELETE FROM sucursales WHERE id_sucursal=?", (id_sucursal,))
        db.commit()
        flash(f'Sucursal «{suc["nombre"]}» eliminada.', 'info')
    except sqlite3.Error as e:
        flash(f'Error: {e}', 'danger')
    finally:
        try: db.close()
        except Exception: pass
    return redirect(url_for('listar_sucursales'))


# ── INICIO ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    with app.app_context():
        migrate_db()
        init_db()
    debug_mode = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug_mode)