from app import app, db, bcrypt, Usuario
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text

def create_db_and_users():
    """
    Inicializa la base de datos y crea los usuarios predeterminados.
    """
    with app.app_context():
        # Creación de la base de datos y las tablas
        # create_all() no elimina tablas existentes, por lo que es seguro de ejecutar.
        db.create_all()
        print('Tablas de la base de datos creadas.')

        # Crear un usuario administrador si no existe
        admin_pw = 'admin123'
        if not Usuario.query.filter_by(username='admin').first():
            pw_hash = bcrypt.generate_password_hash(admin_pw).decode('utf-8')
            admin = Usuario(username='admin', password_hash=pw_hash, rol='admin')
            db.session.add(admin)

        # Crear un usuario trabajador si no existe
        trabajador_pw = 'trabajo123'
        if not Usuario.query.filter_by(username='trabajador').first():
            pw_hash = bcrypt.generate_password_hash(trabajador_pw).decode('utf-8')
            trabajador = Usuario(username='trabajador', password_hash=pw_hash, rol='trabajador')
            db.session.add(trabajador)

        try:
            db.session.commit()
            print('DB inicializada y usuarios creados (admin, trabajador)')
        except IntegrityError:
            db.session.rollback()
            print('Usuarios ya existen')

if __name__ == "__main__":
    create_db_and_users()
