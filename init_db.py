from app import app, db, bcrypt, Usuario, Prestamo, Cliente, Cuota
from sqlalchemy.exc import IntegrityError
from sqlalchemy import text, inspect
from decimal import Decimal
import sys

def agregar_columnas_faltantes():
    """
    Agrega las nuevas columnas necesarias para el sistema mejorado.
    """
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            
            # Verificar columnas de prestamos
            prestamos_columns = [col['name'] for col in inspector.get_columns('prestamos')]
            
            nuevas_columnas_prestamos = []
            
            if 'fecha_pago_completo' not in prestamos_columns:
                nuevas_columnas_prestamos.append('ADD COLUMN fecha_pago_completo DATE')
                
            if 'monto_principal' not in prestamos_columns:
                nuevas_columnas_prestamos.append('ADD COLUMN monto_principal NUMERIC(10,2)')
                
            if 'monto_total' not in prestamos_columns:
                nuevas_columnas_prestamos.append('ADD COLUMN monto_total NUMERIC(10,2)')
                
            if 'tipo_prestamo' not in prestamos_columns:
                nuevas_columnas_prestamos.append("ADD COLUMN tipo_prestamo VARCHAR(10) DEFAULT 'CR'")
                
            if 'tipo_frecuencia' not in prestamos_columns:
                nuevas_columnas_prestamos.append('ADD COLUMN tipo_frecuencia VARCHAR(50)')
                
            if 'cuota_diaria' not in prestamos_columns:
                nuevas_columnas_prestamos.append('ADD COLUMN cuota_diaria NUMERIC(10,2) DEFAULT 0.0')
                
            if 'prestamo_refinanciado_id' not in prestamos_columns:
                nuevas_columnas_prestamos.append('ADD COLUMN prestamo_refinanciado_id INTEGER REFERENCES prestamos(id)')
            
            if nuevas_columnas_prestamos:
                print(f"Agregando {len(nuevas_columnas_prestamos)} columnas a la tabla prestamos...")
                alter_query = f"ALTER TABLE prestamos {', '.join(nuevas_columnas_prestamos)}"
                db.engine.execute(text(alter_query))
                print("Columnas agregadas exitosamente a prestamos.")
            
            # Verificar columnas de cuotas
            if 'cuotas' in inspector.get_table_names():
                cuotas_columns = [col['name'] for col in inspector.get_columns('cuotas')]
                
                if 'estado_pago' not in cuotas_columns:
                    print("Agregando columna estado_pago a la tabla cuotas...")
                    db.engine.execute(text("ALTER TABLE cuotas ADD COLUMN estado_pago VARCHAR(20) DEFAULT 'a_tiempo'"))
                    print("Columna estado_pago agregada exitosamente.")
            
            # Migrar columnas antiguas si existen
            if 'tipo' in prestamos_columns and 'tipo_frecuencia' in prestamos_columns:
                print("Migrando datos de columna 'tipo' a 'tipo_frecuencia'...")
                db.engine.execute(text("UPDATE prestamos SET tipo_frecuencia = tipo WHERE tipo IS NOT NULL AND tipo_frecuencia IS NULL"))
                db.engine.execute(text("ALTER TABLE prestamos DROP COLUMN IF EXISTS tipo"))
                
            if 'cuota' in prestamos_columns and 'cuota_diaria' in prestamos_columns:
                print("Migrando datos de columna 'cuota' a 'cuota_diaria'...")
                db.engine.execute(text("UPDATE prestamos SET cuota_diaria = cuota WHERE cuota IS NOT NULL AND cuota_diaria = 0"))
                db.engine.execute(text("ALTER TABLE prestamos DROP COLUMN IF EXISTS cuota"))
                
        except Exception as e:
            print(f"Error agregando columnas faltantes: {e}")
            db.session.rollback()
            return False
        return True


def crear_tabla_cuotas():
    """
    Crea la tabla de cuotas si no existe.
    """
    with app.app_context():
        try:
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if 'cuotas' not in tables:
                print("Creando tabla de cuotas...")
                db.engine.execute(text("""
                    CREATE TABLE cuotas (
                        id SERIAL PRIMARY KEY,
                        prestamo_id INTEGER NOT NULL REFERENCES prestamos(id) ON DELETE CASCADE,
                        monto NUMERIC(10,2) NOT NULL,
                        fecha_pago DATE NOT NULL DEFAULT CURRENT_DATE,
                        descripcion VARCHAR(200),
                        estado_pago VARCHAR(20) DEFAULT 'a_tiempo'
                    )
                """))
                print("Tabla de cuotas creada exitosamente.")
            else:
                print("La tabla de cuotas ya existe.")
                
        except Exception as e:
            print(f"Error creando tabla de cuotas: {e}")
            return False
        return True


def migrar_prestamos_al_nuevo_formato():
    """
    Migra los préstamos existentes al nuevo formato.
    """
    with app.app_context():
        try:
            print("Migrando préstamos al nuevo formato...")
            
            # Obtener préstamos que necesitan migración
            prestamos_query = text("""
                SELECT id, monto, interes, monto_principal, monto_total, tipo_prestamo, tipo_frecuencia, cuota_diaria
                FROM prestamos 
                WHERE monto_principal IS NULL OR monto_total IS NULL
            """)
            
            result = db.engine.execute(prestamos_query)
            prestamos_a_migrar = result.fetchall()
            
            if not prestamos_a_migrar:
                print("No hay préstamos que necesiten migración.")
                return True
            
            print(f"Migrando {len(prestamos_a_migrar)} préstamos...")
            
            for prestamo in prestamos_a_migrar:
                prestamo_id = prestamo[0]
                monto = Decimal(str(prestamo[1])) if prestamo[1] else Decimal('0')
                interes = Decimal(str(prestamo[2])) if prestamo[2] else Decimal('0')
                
                # Calcular monto principal y total
                if prestamo[3] is None:  # monto_principal es None
                    monto_principal = monto
                else:
                    monto_principal = Decimal(str(prestamo[3]))
                
                if prestamo[4] is None:  # monto_total es None
                    interes_monto = monto_principal * (interes / 100)
                    monto_total = monto_principal + interes_monto
                else:
                    monto_total = Decimal(str(prestamo[4]))
                
                # Valores por defecto
                tipo_prestamo = prestamo[5] if prestamo[5] else 'CR'
                tipo_frecuencia = prestamo[6] if prestamo[6] else 'Diario'
                cuota_diaria = Decimal(str(prestamo[7])) if prestamo[7] else Decimal('0')
                
                # Actualizar el préstamo
                update_query = text("""
                    UPDATE prestamos 
                    SET monto_principal = :monto_principal,
                        monto_total = :monto_total,
                        tipo_prestamo = :tipo_prestamo,
                        tipo_frecuencia = :tipo_frecuencia,
                        cuota_diaria = :cuota_diaria,
                        saldo = COALESCE(saldo, :monto_total)
                    WHERE id = :prestamo_id
                """)
                
                db.engine.execute(update_query, {
                    'prestamo_id': prestamo_id,
                    'monto_principal': monto_principal,
                    'monto_total': monto_total,
                    'tipo_prestamo': tipo_prestamo,
                    'tipo_frecuencia': tipo_frecuencia,
                    'cuota_diaria': cuota_diaria
                })
            
            print(f"Migración de {len(prestamos_a_migrar)} préstamos completada.")
            
        except Exception as e:
            print(f"Error migrando préstamos: {e}")
            db.session.rollback()
            return False
        return True


def migrar_pagos_a_cuotas():
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
                
                # Migrar pagos a cuotas evitando duplicados
                db.engine.execute(text("""
                    INSERT INTO cuotas (prestamo_id, monto, fecha_pago, descripcion, estado_pago)
                    SELECT p.prestamo_id, p.monto, p.fecha_pago, 'Migrado desde pagos', 'a_tiempo'
                    FROM pagos p
                    WHERE NOT EXISTS (
                        SELECT 1 FROM cuotas c
                        WHERE c.prestamo_id = p.prestamo_id 
                        AND c.monto = p.monto 
                        AND c.fecha_pago = p.fecha_pago
                        AND c.descripcion = 'Migrado desde pagos'
                    )
                """))
                
                print("Migración de pagos a cuotas completada.")
            else:
                print("No hay pagos para migrar.")
                
        except Exception as e:
            print(f"Error migrando pagos a cuotas: {e}")
            return False
        return True


def actualizar_saldos_y_estados():
    """
    Actualiza los saldos de préstamos y estados basándose en las cuotas registradas.
    """
    with app.app_context():
        try:
            print("Actualizando saldos y estados de préstamos...")
            
            # Obtener todos los préstamos
            prestamos_query = text("""
                SELECT id, monto_total, estado 
                FROM prestamos 
                WHERE monto_total IS NOT NULL
            """)
            
            result = db.engine.execute(prestamos_query)
            prestamos = result.fetchall()
            
            for prestamo in prestamos:
                prestamo_id = prestamo[0]
                monto_total = Decimal(str(prestamo[1]))
                estado_actual = prestamo[2]
                
                # Calcular total pagado en cuotas
                cuotas_query = text("""
                    SELECT COALESCE(SUM(monto), 0) 
                    FROM cuotas 
                    WHERE prestamo_id = :prestamo_id
                """)
                
                result_cuotas = db.engine.execute(cuotas_query, {'prestamo_id': prestamo_id})
                total_pagado = Decimal(str(result_cuotas.fetchone()[0]))
                
                # Calcular nuevo saldo
                nuevo_saldo = max(Decimal('0'), monto_total - total_pagado)
                
                # Determinar nuevo estado
                if nuevo_saldo <= 0 and estado_actual in ['activo', 'vencido']:
                    nuevo_estado = 'pagado'
                elif estado_actual == 'pagado' and nuevo_saldo > 0:
                    nuevo_estado = 'activo'  # Reactivar si hay saldo pendiente
                else:
                    nuevo_estado = estado_actual
                
                # Actualizar préstamo
                update_query = text("""
                    UPDATE prestamos 
                    SET saldo = :saldo, estado = :estado
                    WHERE id = :prestamo_id
                """)
                
                db.engine.execute(update_query, {
                    'prestamo_id': prestamo_id,
                    'saldo': nuevo_saldo,
                    'estado': nuevo_estado
                })
            
            print(f"Saldos y estados actualizados para {len(prestamos)} préstamos.")
            
        except Exception as e:
            print(f"Error actualizando saldos: {e}")
            db.session.rollback()
            return False
        return True


def crear_usuarios_por_defecto():
    """
    Crea los usuarios por defecto del sistema.
    """
    with app.app_context():
        try:
            print('Creando usuarios por defecto...')
            
            # Crear usuario administrador
            admin_pw = 'admin123'
            if not Usuario.query.filter_by(username='admin').first():
                pw_hash = bcrypt.generate_password_hash(admin_pw).decode('utf-8')
                admin = Usuario(
                    username='admin', 
                    password_hash=pw_hash, 
                    rol='admin',
                    dni='12345678',
                    telefono='999999999'
                )
                db.session.add(admin)
                print('Usuario administrador creado.')
            else:
                print('Usuario administrador ya existe.')

            # Crear usuario trabajador
            trabajador_pw = 'trabajo123'
            if not Usuario.query.filter_by(username='trabajador').first():
                pw_hash = bcrypt.generate_password_hash(trabajador_pw).decode('utf-8')
                trabajador = Usuario(
                    username='trabajador', 
                    password_hash=pw_hash, 
                    rol='trabajador',
                    dni='87654321',
                    telefono='888888888'
                )
                db.session.add(trabajador)
                print('Usuario trabajador creado.')
            else:
                print('Usuario trabajador ya existe.')

            db.session.commit()
            
        except IntegrityError as e:
            db.session.rollback()
            print(f'Error de integridad al crear usuarios: {e}')
            return False
        except Exception as e:
            db.session.rollback()
            print(f'Error al crear usuarios: {e}')
            return False
        return True


def verificar_integridad_datos():
    """
    Verifica la integridad de los datos después de la migración.
    """
    with app.app_context():
        try:
            print("Verificando integridad de datos...")
            
            # Verificar préstamos sin monto_total
            result = db.engine.execute(text("""
                SELECT COUNT(*) FROM prestamos 
                WHERE monto_total IS NULL OR monto_total = 0
            """)).fetchone()
            
            if result[0] > 0:
                print(f"ADVERTENCIA: {result[0]} préstamos sin monto total válido.")
                return False
            
            # Verificar préstamos con saldo negativo
            result = db.engine.execute(text("""
                SELECT COUNT(*) FROM prestamos 
                WHERE saldo < 0
            """)).fetchone()
            
            if result[0] > 0:
                print(f"ADVERTENCIA: {result[0]} préstamos con saldo negativo. Corrigiendo...")
                db.engine.execute(text("UPDATE prestamos SET saldo = 0 WHERE saldo < 0"))
            
            # Verificar cuotas huérfanas
            result = db.engine.execute(text("""
                SELECT COUNT(*) FROM cuotas c
                LEFT JOIN prestamos p ON c.prestamo_id = p.id
                WHERE p.id IS NULL
            """)).fetchone()
            
            if result[0] > 0:
                print(f"ADVERTENCIA: {result[0]} cuotas sin préstamo asociado.")
                return False
            
            print("Verificación de integridad completada exitosamente.")
            
        except Exception as e:
            print(f"Error verificando integridad: {e}")
            return False
        return True


def generar_datos_de_prueba():
    """
    Genera algunos datos de prueba para facilitar las pruebas del sistema.
    """
    with app.app_context():
        try:
            # Solo crear datos de prueba si no hay clientes
            if Cliente.query.count() > 0:
                print("Ya existen clientes en la base de datos. Omitiendo datos de prueba.")
                return True
            
            print("Creando datos de prueba...")
            
            # Cliente 1
            cliente1 = Cliente(
                nombre="Juan Pérez García",
                dni="12345678",
                direccion="Av. Los Olivos 123, Lima",
                telefono="987654321"
            )
            db.session.add(cliente1)
            db.session.flush()
            
            # Préstamo para cliente 1
            prestamo1 = Prestamo(
                cliente_id=cliente1.id,
                monto_principal=Decimal('1000.00'),
                interes=Decimal('20.00'),
                monto_total=Decimal('1200.00'),
                fecha_inicio=db.func.current_date(),
                saldo=Decimal('1200.00'),
                tipo_prestamo='CR',
                tipo_frecuencia='Diario',
                cuota_diaria=Decimal('40.00'),
                estado='activo'
            )
            db.session.add(prestamo1)
            
            # Cliente 2 - con préstamo pagado
            cliente2 = Cliente(
                nombre="María López Silva",
                dni="87654321",
                direccion="Jr. Las Flores 456, Lima",
                telefono="912345678"
            )
            db.session.add(cliente2)
            db.session.flush()
            
            # Préstamo pagado para cliente 2
            prestamo2 = Prestamo(
                cliente_id=cliente2.id,
                monto_principal=Decimal('500.00'),
                interes=Decimal('15.00'),
                monto_total=Decimal('575.00'),
                fecha_inicio=db.func.current_date() - text("INTERVAL '30 days'"),
                saldo=Decimal('0.00'),
                tipo_prestamo='CR',
                tipo_frecuencia='Diario',
                cuota_diaria=Decimal('25.00'),
                estado='pagado',
                fecha_pago_completo=db.func.current_date()
            )
            db.session.add(prestamo2)
            db.session.flush()
            
            # Cuotas para el préstamo pagado
            for i in range(23):  # 23 cuotas de 25 = 575
                cuota = Cuota(
                    prestamo_id=prestamo2.id,
                    monto=Decimal('25.00'),
                    fecha_pago=db.func.current_date() - text(f"INTERVAL '{22-i} days'"),
                    descripcion=f"Cuota día {i+1}",
                    estado_pago='a_tiempo'
                )
                db.session.add(cuota)
            
            db.session.commit()
            print("Datos de prueba creados exitosamente.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creando datos de prueba: {e}")
            return False
        return True


def ejecutar_migracion_completa():
    """
    Ejecuta la migración completa del sistema.
    """
    print("=" * 60)
    print("INICIANDO MIGRACIÓN COMPLETA DEL SISTEMA DE PRÉSTAMOS")
    print("=" * 60)
    
    pasos = [
        ("Creando tablas de la base de datos", lambda: db.create_all()),
        ("Creando tabla de cuotas", crear_tabla_cuotas),
        ("Agregando columnas faltantes", agregar_columnas_faltantes),
        ("Migrando préstamos al nuevo formato", migrar_prestamos_al_nuevo_formato),
        ("Migrando pagos a cuotas", migrar_pagos_a_cuotas),
        ("Actualizando saldos y estados", actualizar_saldos_y_estados),
        ("Creando usuarios por defecto", crear_usuarios_por_defecto),
        ("Verificando integridad de datos", verificar_integridad_datos),
        ("Generando datos de prueba", generar_datos_de_prueba)
    ]
    
    errores = []
    
    for i, (descripcion, funcion) in enumerate(pasos, 1):
        print(f"\n{i}. {descripcion}...")
        try:
            with app.app_context():
                if callable(funcion):
                    resultado = funcion()
                    if resultado is False:
                        errores.append(descripcion)
                        print(f"   ❌ FALLÓ: {descripcion}")
                    else:
                        print(f"   ✅ COMPLETADO: {descripcion}")
                else:
                    resultado = funcion
                    print(f"   ✅ COMPLETADO: {descripcion}")
        except Exception as e:
            errores.append(f"{descripcion}: {str(e)}")
            print(f"   ❌ ERROR: {descripcion} - {str(e)}")
    
    print("\n" + "=" * 60)
    if errores:
        print("MIGRACIÓN COMPLETADA CON ERRORES:")
        for error in errores:
            print(f"  - {error}")
    else:
        print("🎉 MIGRACIÓN COMPLETADA EXITOSAMENTE")
    
    print("=" * 60)
    print("\n📋 INFORMACIÓN DEL SISTEMA:")
    print("Credenciales de acceso:")
    print("  👨‍💼 Administrador - Usuario: admin, Contraseña: admin123")
    print("  👨‍🔧 Trabajador - Usuario: trabajador, Contraseña: trabajo123")
    
    print("\n🚀 Características del nuevo sistema:")
    print("  ✓ Monto Total = Monto Principal + Intereses")
    print("  ✓ Tipos de préstamo: CR (Crédito Reciente) y REF (Refinanciación)")
    print("  ✓ Sistema de cuotas diarias con seguimiento automático")
    print("  ✓ Cálculo automático de días transcurridos y deuda vencida")
    print("  ✓ Estados de pago: a tiempo, con retraso, anticipado")
    print("  ✓ Función de refinanciación de préstamos")
    print("  ✓ Control de zona horaria (America/Lima)")
    print("  ✓ Estados de préstamo: activo, pagado, refinanciado, vencido")
    print("  ✓ Notificaciones de préstamo completado")
    print("  ✓ Validación de saldos (no pueden ser negativos)")
    
    return len(errores) == 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--solo-usuarios":
        print("Creando solo usuarios por defecto...")
        with app.app_context():
            db.create_all()
            crear_usuarios_por_defecto()
    else:
        ejecutar_migracion_completa()