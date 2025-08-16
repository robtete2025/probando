from app import app, db, bcrypt, Usuario, Prestamo
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text
from decimal import Decimal

def migrate_prestamos_to_new_format():
    """
    Migra los préstamos existentes al nuevo formato con monto_principal, monto_total, etc.
    """
    with app.app_context():
        try:
            # Verificar si ya existen las nuevas columnas
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('prestamos')]
            
            # Si las columnas nuevas no existen, ejecutar ALTER TABLE
            if 'monto_principal' not in columns:
                print("Agregando nuevas columnas a la tabla prestamos...")
                
                # Agregar nuevas columnas
                db.engine.execute(text("""
                    ALTER TABLE prestamos 
                    ADD COLUMN monto_principal NUMERIC(10,2),
                    ADD COLUMN monto_total NUMERIC(10,2),
                    ADD COLUMN tipo_prestamo VARCHAR(10) DEFAULT 'CR',
                    ADD COLUMN tipo_frecuencia VARCHAR(50),
                    ADD COLUMN cuota_diaria NUMERIC(10,2) DEFAULT 0.0,
                    ADD COLUMN prestamo_refinanciado_id INTEGER REFERENCES prestamos(id)
                """))
                
                # Renombrar columna 'tipo' a 'tipo_frecuencia' si existe
                if 'tipo' in columns:
                    db.engine.execute(text("""
                        UPDATE prestamos SET tipo_frecuencia = tipo WHERE tipo IS NOT NULL
                    """))
                    db.engine.execute(text("ALTER TABLE prestamos DROP COLUMN tipo"))
                
                # Renombrar columna 'cuota' a 'cuota_diaria' si existe
                if 'cuota' in columns:
                    db.engine.execute(text("""
                        UPDATE prestamos SET cuota_diaria = cuota WHERE cuota IS NOT NULL
                    """))
                    db.engine.execute(text("ALTER TABLE prestamos DROP COLUMN cuota"))
                
                print("Nuevas columnas agregadas exitosamente.")
            
            # Migrar datos existentes
            print("Migrando datos de préstamos existentes...")
            prestamos = Prestamo.query.filter(Prestamo.monto_principal.is_(None)).all()
            
            for prestamo in prestamos:
                # Si monto_principal es None, asumir que 'monto' es el monto original sin interés
                if prestamo.monto_principal is None:
                    prestamo.monto_principal = prestamo.monto if hasattr(prestamo, 'monto') else Decimal('0')
                    
                    # Calcular monto total con interés
                    if prestamo.interes and prestamo.monto_principal:
                        interes_monto = prestamo.monto_principal * (prestamo.interes / 100)
                        prestamo.monto_total = prestamo.monto_principal + interes_monto
                    else:
                        prestamo.monto_total = prestamo.monto_principal
                
                # Establecer valores por defecto
                if not prestamo.tipo_prestamo:
                    prestamo.tipo_prestamo = 'CR'
                
                if not prestamo.tipo_frecuencia:
                    prestamo.tipo_frecuencia = 'Diario'
                
                if not prestamo.cuota_diaria:
                    prestamo.cuota_diaria = Decimal('0')
            
            db.session.commit()
            print(f"Migrados {len(prestamos)} préstamos al nuevo formato.")
            
        except Exception as e:
            print(f"Error durante la migración: {e}")
            db.session.rollback()


def create_cuotas_table():
    """
    Crea la nueva tabla de cuotas si no existe.
    """
    with app.app_context():
        try:
            # Verificar si la tabla cuotas existe
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'cuotas' not in tables:
                print("Creando tabla de cuotas...")
                db.engine.execute(text("""
                    CREATE TABLE cuotas (
                        id SERIAL PRIMARY KEY,
                        prestamo_id INTEGER NOT NULL REFERENCES prestamos(id) ON DELETE CASCADE,
                        monto NUMERIC(10,2) NOT NULL,
                        fecha_pago DATE NOT NULL DEFAULT CURRENT_DATE,
                        descripcion VARCHAR(200)
                    )
                """))
                print("Tabla de cuotas creada exitosamente.")
            else:
                print("La tabla de cuotas ya existe.")
                
        except Exception as e:
            print(f"Error creando tabla de cuotas: {e}")


def migrate_pagos_to_cuotas():
    """
    Migra los pagos existentes a la nueva tabla de cuotas.
    """
    with app.app_context():
        try:
            # Verificar si hay pagos para migrar
            result = db.engine.execute(text("SELECT COUNT(*) FROM pagos")).fetchone()
            pagos_count = result[0] if result else 0
            
            if pagos_count > 0:
                print(f"Migrando {pagos_count} pagos a cuotas...")
                
                # Migrar pagos a cuotas
                db.engine.execute(text("""
                    INSERT INTO cuotas (prestamo_id, monto, fecha_pago, descripcion)
                    SELECT prestamo_id, monto, fecha_pago, 'Migrado desde pagos'
                    FROM pagos
                    WHERE NOT EXISTS (
                        SELECT 1 FROM cuotas 
                        WHERE cuotas.prestamo_id = pagos.prestamo_id 
                        AND cuotas.monto = pagos.monto 
                        AND cuotas.fecha_pago = pagos.fecha_pago
                    )
                """))
                
                print("Migración de pagos a cuotas completada.")
            else:
                print("No hay pagos para migrar.")
                
        except Exception as e:
            print(f"Error migrando pagos a cuotas: {e}")


def actualizar_saldos_prestamos():
    """
    Actualiza los saldos de préstamos basándose en las cuotas registradas.
    """
    with app.app_context():
        try:
            print("Actualizando saldos de préstamos...")
            
            prestamos_activos = Prestamo.query.filter_by(estado='activo').all()
            
            for prestamo in prestamos_activos:
                # Calcular total pagado en cuotas
                result = db.engine.execute(text("""
                    SELECT COALESCE(SUM(monto), 0) 
                    FROM cuotas 
                    WHERE prestamo_id = :prestamo_id
                """), {'prestamo_id': prestamo.id}).fetchone()
                
                total_pagado = Decimal(str(result[0])) if result and result[0] else Decimal('0')
                
                # Actualizar saldo
                if prestamo.monto_total:
                    nuevo_saldo = prestamo.monto_total - total_pagado
                    prestamo.saldo = max(Decimal('0'), nuevo_saldo)
                    
                    # Si el saldo es 0, marcar como pagado
                    if prestamo.saldo == 0:
                        prestamo.estado = 'pagado'
            
            db.session.commit()
            print(f"Saldos actualizados para {len(prestamos_activos)} préstamos activos.")
            
        except Exception as e:
            print(f"Error actualizando saldos: {e}")
            db.session.rollback()


def create_db_and_users():
    """
    Inicializa la base de datos y crea los usuarios predeterminados.
    """
    with app.app_context():
        # Creación de la base de datos y las tablas
        print('Creando tablas de la base de datos...')
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
            print('Usuarios creados (admin, trabajador)')
        except IntegrityError:
            db.session.rollback()
            print('Usuarios ya existen')


def run_full_migration():
    """
    Ejecuta la migración completa del sistema.
    """
    print("=== INICIANDO MIGRACIÓN DEL SISTEMA DE PRÉSTAMOS ===")
    
    # 1. Crear tablas básicas y usuarios
    create_db_and_users()
    
    # 2. Crear tabla de cuotas
    create_cuotas_table()
    
    # 3. Migrar estructura de préstamos
    migrate_prestamos_to_new_format()
    
    # 4. Migrar pagos a cuotas
    migrate_pagos_to_cuotas()
    
    # 5. Actualizar saldos
    actualizar_saldos_prestamos()
    
    print("=== MIGRACIÓN COMPLETADA EXITOSAMENTE ===")
    print("\nCredenciales de acceso:")
    print("Administrador - Usuario: admin, Contraseña: admin123")
    print("Trabajador - Usuario: trabajador, Contraseña: trabajo123")
    print("\nCaracterísticas del nuevo sistema:")
    print("- Monto Total = Monto Principal + Intereses")
    print("- Tipos de préstamo: CR (Crédito Reciente) y REF (Refinanciación)")
    print("- Sistema de cuotas diarias con seguimiento automático")
    print("- Cálculo automático de días transcurridos y deuda vencida")
    print("- Función de refinanciación de préstamos")


if __name__ == "__main__":
    run_full_migration()