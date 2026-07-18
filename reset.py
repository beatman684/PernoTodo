import sqlite3, hashlib

conn = sqlite3.connect('database/pernotodo.db')
conn.row_factory = sqlite3.Row

users = conn.execute('SELECT email, nombre, role FROM usuario').fetchall()
print('=== USUARIOS ACTUALES ===')
for u in users:
    print(f'  {u["email"]} | {u["nombre"]} | {u["role"]}')

pwd = hashlib.sha256('Admin2024'.encode()).hexdigest()[:24]

# Intentar con 'password' primero
try:
    conn.execute("UPDATE usuario SET password=? WHERE role='Administrador'", (pwd,))
    conn.commit()
    print('\nContrasena reseteada con campo: password')
except Exception as e:
    print(f'Error con password: {e}')
    try:
        conn.execute("UPDATE usuario SET password_hash=? WHERE role='Administrador'", (pwd,))
        conn.commit()
        print('\nContrasena reseteada con campo: password_hash')
    except Exception as e2:
        print(f'Error con password_hash: {e2}')

conn.close()
print('Listo. Usa: admin@pernotodo.com / Admin2024')