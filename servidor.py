"""
Servidor de producción de PERNO TODO (Waitress).
Usado por el arranque automático en la computadora del negocio.
Uso manual:  venv\\Scripts\\python.exe servidor.py
"""
from waitress import serve
from app import app
from database.connection import migrate_db, init_db

if __name__ == '__main__':
    migrate_db()
    init_db()
    print('PERNO TODO corriendo en http://localhost:5000  (Ctrl+C para detener)')
    serve(app, host='0.0.0.0', port=5000, threads=6)
