from flask import Flask, render_template, redirect, url_for, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies,
    verify_jwt_in_request, get_jwt, jwt_required
)
from datetime import timedelta, datetime, timezone, date
import os
from sqlalchemy import func, or_
from decimal import Decimal

app = Flask(__name__, static_folder='static', template_folder='templates')

# Configuración de la base de datos
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'prestamos_db')
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de JWT en cookies (entorno de desarrollo)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'prestamo123')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)  # Aumentado a 30 min
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)


# ---------------- MODELOS ----------------
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    dni = db.Column(db.String(15), unique=True, nullable=True)
    telefono = db.Column(db.String(20), nullable=True)


class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(15), unique=True, nullable=False)
    direccion = db.Column(db.Text)
    telefono = db.Column(db.String(20))
    fecha_registro = db.Column(db.DateTime, server_default=db.func.now())

    prestamos = db.relationship('Prestamo', backref=db.backref('cliente', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'dni': self.dni,
            'direccion': self.direccion,
            'telefono': self.telefono,
            'fecha_registro': self.fecha_registro.isoformat() if self.fecha_registro else None,
            'prestamos': [p.to_dict() for p in self.prestamos]
        }


class Prestamo(db.Model):
    __tablename__ = 'prestamos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id', ondelete='CASCADE'), nullable=False)
    monto_principal = db.Column(db.Numeric(10, 2), nullable=False)  # Monto original sin interés
    interes = db.Column(db.Numeric(5, 2), nullable=False)  # Porcentaje de interés
    monto_total = db.Column(db.Numeric(10, 2), nullable=False)  # Monto + intereses
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date)
    estado = db.Column(db.String(50), nullable=False, server_default='activo')
    
    # Campos mejorados para control del préstamo
    saldo = db.Column(db.Numeric(10, 2), default=0.0)  # Monto pendiente de pago
    tipo_prestamo = db.Column(db.String(10), default='CR')  # CR (Crédito Reciente) o REF (Refinanciación)
    tipo_frecuencia = db.Column(db.String(50), nullable=True)  # Diario, Semanal, Quincenal, Mensual
    dt = db.Column(db.Integer, default=0)  # Días transcurridos desde inicio
    cuota_diaria = db.Column(db.Numeric(10, 2), default=0.0)  # Cuota que debe pagar por día
    deuda_vencida = db.Column(db.Numeric(10, 2), default=0.0)  # Deuda acumulada por pagos insuficientes
    prestamo_refinanciado_id = db.Column(db.Integer, db.ForeignKey('prestamos.id'), nullable=True)  # Para refinanciaciones

    cuotas = db.relationship('Cuota', backref=db.backref('prestamo', lazy=True))

    def calcular_dias_transcurridos(self):
        """Calcula y actualiza los días transcurridos desde el inicio del préstamo"""
        if self.fecha_inicio:
            hoy = date.today()
            self.dt = (hoy - self.fecha_inicio).days
        return self.dt

    def calcular_deuda_vencida(self):
        """Calcula la deuda vencida basada en cuotas no pagadas completamente"""
        if self.estado != 'activo':
            return 0.0
            
        dias_transcurridos = self.calcular_dias_transcurridos()
        deuda_esperada = Decimal(str(dias_transcurridos)) * self.cuota_diaria
        total_pagado = sum(Decimal(str(cuota.monto)) for cuota in self.cuotas)
        
        deuda_vencida = max(0, deuda_esperada - total_pagado)
        self.deuda_vencida = deuda_vencida
        return deuda_vencida

    def to_dict(self):
        self.calcular_dias_transcurridos()
        self.calcular_deuda_vencida()
        
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'monto_principal': float(self.monto_principal),
            'monto_total': float(self.monto_total),
            'interes': float(self.interes),
            'fecha_inicio': self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            'fecha_fin': self.fecha_fin.isoformat() if self.fecha_fin else None,
            'estado': self.estado,
            'saldo': float(self.saldo),
            'tipo_prestamo': self.tipo_prestamo,
            'tipo_frecuencia': self.tipo_frecuencia,
            'dt': self.dt,
            'cuota_diaria': float(self.cuota_diaria),
            'deuda_vencida': float(self.deuda_vencida),
            'prestamo_refinanciado_id': self.prestamo_refinanciado_id,
            'total_cuotas': len(self.cuotas),
            'cuotas': [c.to_dict() for c in self.cuotas]
        }


class Cuota(db.Model):
    __tablename__ = 'cuotas'
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamos.id', ondelete='CASCADE'), nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.Date, nullable=False, server_default=db.func.current_date())
    descripcion = db.Column(db.String(200), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'prestamo_id': self.prestamo_id,
            'monto': float(self.monto),
            'fecha_pago': self.fecha_pago.isoformat() if self.fecha_pago else None,
            'descripcion': self.descripcion
        }


# Mantener tabla de pagos para compatibilidad (puede ser eliminada después)
class Pago(db.Model):
    __tablename__ = 'pagos'
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamos.id', ondelete='CASCADE'), nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.Date, nullable=False, server_default=db.func.current_date())

    def to_dict(self):
        return {
            'id': self.id,
            'prestamo_id': self.prestamo_id,
            'monto': float(self.monto),
            'fecha_pago': self.fecha_pago.isoformat() if self.fecha_pago else None
        }


# ---------------- AUTENTICACIÓN (cookies) ----------------
@app.route('/auth/login', methods=['POST'])
def login():
    """Ruta para iniciar sesión y establecer el token JWT en las cookies."""
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'msg': 'faltan campos'}), 400

    usuario = Usuario.query.filter_by(username=username).first()
    if usuario and bcrypt.check_password_hash(usuario.password_hash, password):
        token = create_access_token(identity=usuario.username, additional_claims={'rol': usuario.rol})
        resp = jsonify({'rol': usuario.rol})
        set_access_cookies(resp, token)
        return resp, 200

    return jsonify({'msg': 'Credenciales inválidas'}), 401


@app.route('/auth/check', methods=['GET'])
@jwt_required()
def check_auth():
    """Ruta para verificar la autenticación del usuario."""
    rol = get_jwt().get('rol')
    return jsonify({'rol': rol}), 200


@app.route('/auth/logout', methods=['POST'])
def logout():
    """Ruta para cerrar sesión y eliminar el token JWT de las cookies."""
    resp = jsonify({'msg': 'logout'})
    unset_jwt_cookies(resp)
    return resp, 200


@jwt_required(optional=True)
@app.after_request
def refresh_expiring_jwts(response):
    """
    Refresca automáticamente el token JWT si está próximo a expirar.
    Verifica si el token expirará en los próximos 5 minutos y genera uno nuevo.
    """
    try:
        exp_timestamp = get_jwt()["exp"]
        now = datetime.now(timezone.utc)
        target_timestamp = datetime.timestamp(now + timedelta(minutes=5))
        if target_timestamp > exp_timestamp:
            access_token = create_access_token(
                identity=get_jwt()['sub'],
                additional_claims={"rol": get_jwt().get("rol")}
            )
            set_access_cookies(response, access_token)
        return response
    except (RuntimeError, KeyError):
        return response


# ---------------- FUNCIONES AUXILIARES ----------------
def calcular_monto_total(monto_principal, interes):
    """Calcula el monto total incluyendo intereses"""
    monto_principal = Decimal(str(monto_principal))
    interes = Decimal(str(interes))
    interes_monto = monto_principal * (interes / 100)
    return monto_principal + interes_monto


def calcular_fecha_fin(fecha_inicio, tipo_frecuencia, monto_total, cuota_diaria):
    """
    Calcula la fecha de vencimiento del préstamo basado en monto total y cuota diaria
    """
    monto_total = Decimal(str(monto_total))
    cuota_diaria = Decimal(str(cuota_diaria))
    
    if cuota_diaria <= 0:
        return fecha_inicio + timedelta(days=30)  # Por defecto 30 días
    
    dias_necesarios = int(monto_total / cuota_diaria)
    if monto_total % cuota_diaria > 0:
        dias_necesarios += 1  # Redondear hacia arriba
    
    fecha_fin = fecha_inicio + timedelta(days=dias_necesarios)
    return fecha_fin


def actualizar_prestamos_activos():
    """Actualiza días transcurridos y deuda vencida para todos los préstamos activos"""
    prestamos_activos = Prestamo.query.filter_by(estado='activo').all()
    
    for prestamo in prestamos_activos:
        prestamo.calcular_dias_transcurridos()
        prestamo.calcular_deuda_vencida()
    
    db.session.commit()


# ---------------- API ENDPOINTS ----------------

@app.route('/api/clientes_con_prestamo', methods=['POST'])
@jwt_required()
def crear_cliente_con_prestamo():
    """Crea un nuevo cliente y un nuevo préstamo en una sola operación."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    data = request.get_json() or {}

    cliente_data = data.get('cliente', {})
    nombre = cliente_data.get('nombre')
    dni = cliente_data.get('dni')
    telefono = cliente_data.get('telefono')
    direccion = cliente_data.get('direccion')

    if not nombre or not dni:
        return jsonify({'msg': 'Faltan campos de cliente'}), 400
    if Cliente.query.filter_by(dni=dni).first():
        return jsonify({'msg': 'Cliente con ese DNI ya existe'}), 400

    prestamo_data = data.get('prestamo', {})
    monto_principal = prestamo_data.get('monto')
    interes = prestamo_data.get('interes')
    cuota_diaria = prestamo_data.get('cuota')
    fecha_inicio_str = prestamo_data.get('fecha_inicio')

    if not monto_principal or not interes or not cuota_diaria or not fecha_inicio_str:
        return jsonify({'msg': 'Faltan campos de préstamo'}), 400

    try:
        fecha_inicio = datetime.fromisoformat(fecha_inicio_str).date()
        tipo_frecuencia = prestamo_data.get('tipo_frecuencia', 'Diario')
        
        # Calcular monto total con intereses
        monto_total = calcular_monto_total(monto_principal, interes)
        
        # Calcular fecha de vencimiento
        fecha_fin = calcular_fecha_fin(fecha_inicio, tipo_frecuencia, monto_total, cuota_diaria)

        nuevo_cliente = Cliente(
            nombre=nombre,
            dni=dni,
            telefono=telefono,
            direccion=direccion
        )
        db.session.add(nuevo_cliente)
        db.session.flush()  # Para obtener el ID del cliente

        nuevo_prestamo = Prestamo(
            cliente_id=nuevo_cliente.id,
            monto_principal=monto_principal,
            interes=interes,
            monto_total=monto_total,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            saldo=monto_total,
            tipo_prestamo='CR',  # Crédito Reciente por defecto
            tipo_frecuencia=tipo_frecuencia,
            cuota_diaria=cuota_diaria,
            dt=0
        )
        db.session.add(nuevo_prestamo)
        db.session.commit()

        return jsonify({'msg': 'Cliente y préstamo creados', 'cliente': nuevo_cliente.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al crear el cliente y el préstamo', 'error': str(e)}), 500


@app.route('/api/clientes', methods=['GET'])
@jwt_required()
def api_clientes():
    """
    Obtiene los clientes que tienen al menos un préstamo activo.
    Actualiza automáticamente días transcurridos y deuda vencida.
    """
    # Actualizar todos los préstamos activos antes de mostrar
    actualizar_prestamos_activos()
    
    clientes_bd = Cliente.query.all()
    clientes_con_prestamos_activos = []

    for cliente in clientes_bd:
        # Filtrar solo préstamos activos
        prestamos_activos = [p for p in cliente.prestamos if p.estado == 'activo']

        if prestamos_activos:
            cliente_data = {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'dni': cliente.dni,
                'direccion': cliente.direccion,
                'telefono': cliente.telefono,
                'fecha_registro': cliente.fecha_registro.isoformat() if cliente.fecha_registro else None,
                'prestamos': [p.to_dict() for p in prestamos_activos]
            }
            clientes_con_prestamos_activos.append(cliente_data)

    return jsonify(clientes_con_prestamos_activos), 200


@app.route('/api/prestamos/<int:prestamo_id>/cuota', methods=['POST'])
@jwt_required()
def registrar_cuota(prestamo_id):
    """
    Registra una cuota (minipago) para un préstamo específico.
    Permitido para roles 'admin' y 'trabajador'.
    """
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    prestamo = Prestamo.query.get_or_404(prestamo_id)
    data = request.get_json() or {}
    monto_cuota = data.get('monto')

    if not monto_cuota or float(monto_cuota) <= 0:
        return jsonify({'msg': 'Monto de cuota inválido'}), 400

    try:
        monto_cuota = Decimal(str(monto_cuota))
        prestamo.calcular_dias_transcurridos()

        # Actualizar el saldo del préstamo
        if prestamo.saldo <= monto_cuota:
            monto_real_cuota = prestamo.saldo
            prestamo.saldo = Decimal('0.0')
            prestamo.estado = 'pagado'
        else:
            monto_real_cuota = monto_cuota
            prestamo.saldo -= monto_real_cuota

        # Crear el registro de la cuota
        nueva_cuota = Cuota(
            prestamo_id=prestamo_id,
            monto=monto_real_cuota,
            fecha_pago=date.today(),
            descripcion=data.get('descripcion', 'Cuota diaria')
        )
        db.session.add(nueva_cuota)
        
        # Recalcular deuda vencida después del pago
        prestamo.calcular_deuda_vencida()
        
        db.session.commit()

        return jsonify({
            'msg': 'Cuota registrada exitosamente',
            'prestamo': prestamo.to_dict(),
            'cuota': nueva_cuota.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al registrar la cuota', 'error': str(e)}), 500


@app.route('/api/prestamos/<int:prestamo_id>/refinanciar', methods=['POST'])
@jwt_required()
def refinanciar_prestamo(prestamo_id):
    """
    Refinancia un préstamo existente. Marca el préstamo original como 'refinanciado'
    y crea un nuevo préstamo REF con el saldo pendiente más nuevos intereses.
    """
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    prestamo_original = Prestamo.query.get_or_404(prestamo_id)
    
    if prestamo_original.estado != 'activo':
        return jsonify({'msg': 'Solo se pueden refinanciar préstamos activos'}), 400
    
    if prestamo_original.saldo <= 0:
        return jsonify({'msg': 'El préstamo ya está pagado completamente'}), 400

    data = request.get_json() or {}
    nuevo_interes = data.get('interes')
    nueva_cuota_diaria = data.get('cuota_diaria')

    if not nuevo_interes or not nueva_cuota_diaria:
        return jsonify({'msg': 'Faltan campos: interes y cuota_diaria'}), 400

    try:
        # Actualizar el préstamo original
        prestamo_original.calcular_dias_transcurridos()
        prestamo_original.estado = 'refinanciado'
        
        # Calcular nuevo monto total con intereses sobre el saldo pendiente
        saldo_pendiente = prestamo_original.saldo
        nuevo_monto_total = calcular_monto_total(saldo_pendiente, nuevo_interes)
        
        # Calcular nueva fecha de vencimiento
        fecha_inicio_refinanciacion = date.today()
        fecha_fin_refinanciacion = calcular_fecha_fin(
            fecha_inicio_refinanciacion, 
            prestamo_original.tipo_frecuencia, 
            nuevo_monto_total, 
            nueva_cuota_diaria
        )

        # Crear el préstamo refinanciado
        prestamo_refinanciado = Prestamo(
            cliente_id=prestamo_original.cliente_id,
            monto_principal=saldo_pendiente,
            interes=nuevo_interes,
            monto_total=nuevo_monto_total,
            fecha_inicio=fecha_inicio_refinanciacion,
            fecha_fin=fecha_fin_refinanciacion,
            saldo=nuevo_monto_total,
            tipo_prestamo='REF',  # Refinanciación
            tipo_frecuencia=prestamo_original.tipo_frecuencia,
            cuota_diaria=nueva_cuota_diaria,
            dt=0,
            prestamo_refinanciado_id=prestamo_original.id
        )
        
        db.session.add(prestamo_refinanciado)
        db.session.commit()

        return jsonify({
            'msg': 'Préstamo refinanciado exitosamente',
            'prestamo_original': prestamo_original.to_dict(),
            'prestamo_refinanciado': prestamo_refinanciado.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al refinanciar el préstamo', 'error': str(e)}), 500


@app.route('/api/prestamos/<int:prestamo_id>/pagado_manual', methods=['PUT'])
@jwt_required()
def marcar_prestamo_pagado(prestamo_id):
    """
    Marca manualmente un préstamo como 'pagado' (solo para administradores).
    Si es una refinanciación, también marca el préstamo original como pagado.
    """
    try:
        claims = get_jwt()
        if claims.get('rol') != 'admin':
            return jsonify({'msg': 'No autorizado'}), 403

        prestamo = Prestamo.query.get(prestamo_id)
        if not prestamo:
            return jsonify({'msg': 'Préstamo no encontrado'}), 404

        prestamo.estado = 'pagado'
        prestamo.saldo = Decimal('0.0')
        prestamo.deuda_vencida = Decimal('0.0')
        
        # Si es una refinanciación, también marcar el préstamo original como pagado
        if prestamo.tipo_prestamo == 'REF' and prestamo.prestamo_refinanciado_id:
            prestamo_original = Prestamo.query.get(prestamo.prestamo_refinanciado_id)
            if prestamo_original:
                prestamo_original.estado = 'pagado'
                prestamo_original.saldo = Decimal('0.0')
                prestamo_original.deuda_vencida = Decimal('0.0')

        db.session.commit()

        return jsonify({'msg': 'Préstamo marcado como pagado exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al marcar el préstamo como pagado', 'error': str(e)}), 500


@app.route('/api/prestamos', methods=['POST'])
@jwt_required()
def api_create_prestamo():
    """Crea un nuevo préstamo para un cliente existente."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403
    
    data = request.get_json() or {}
    required = ['cliente_id', 'monto', 'interes', 'cuota_diaria', 'fecha_inicio']
    if not all(k in data for k in required):
        return jsonify({'msg': 'faltan campos: cliente_id, monto, interes, cuota_diaria, fecha_inicio'}), 400
    
    cliente = Cliente.query.get(data['cliente_id'])
    if not cliente:
        return jsonify({'msg': 'cliente no existe'}), 404

    try:
        fecha_inicio = datetime.fromisoformat(data['fecha_inicio']).date()
        tipo_frecuencia = data.get('tipo_frecuencia', 'Diario')
        monto_principal = Decimal(str(data['monto']))
        interes = Decimal(str(data['interes']))
        cuota_diaria = Decimal(str(data['cuota_diaria']))
        
        # Calcular monto total
        monto_total = calcular_monto_total(monto_principal, interes)
        fecha_fin = calcular_fecha_fin(fecha_inicio, tipo_frecuencia, monto_total, cuota_diaria)

        p = Prestamo(
            cliente_id=data['cliente_id'],
            monto_principal=monto_principal,
            interes=interes,
            monto_total=monto_total,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado=data.get('estado', 'activo'),
            saldo=monto_total,
            tipo_prestamo='CR',  # Crédito Reciente por defecto
            tipo_frecuencia=tipo_frecuencia,
            cuota_diaria=cuota_diaria,
            dt=0
        )
        db.session.add(p)
        db.session.commit()
        return jsonify(p.to_dict()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al crear préstamo', 'error': str(e)}), 500


# Mantener compatibilidad con pagos antiguos
@app.route('/api/prestamos/<int:prestamo_id>/pagar', methods=['POST'])
@jwt_required()
def api_pagar_prestamo(prestamo_id):
    """Redirige a la nueva API de cuotas para mantener compatibilidad"""
    return registrar_cuota(prestamo_id)


# Resto de endpoints sin cambios significativos...
@app.route('/api/clientes/search', methods=['GET'])
@jwt_required()
def api_search_clientes():
    """Busca clientes por nombre o DNI y devuelve TODOS sus préstamos."""
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify([]), 200
    
    clientes_encontrados = Cliente.query.filter(or_(
        Cliente.nombre.ilike(f'%{search_term}%'),
        Cliente.dni.ilike(f'%{search_term}%')
    )).all()

    resultados_busqueda = []
    for cliente in clientes_encontrados:
        cliente_data = {
            'id': cliente.id,
            'nombre': cliente.nombre,
            'dni': cliente.dni,
            'direccion': cliente.direccion,
            'telefono': cliente.telefono,
            'fecha_registro': cliente.fecha_registro.isoformat() if cliente.fecha_registro else None,
            'prestamos': [p.to_dict() for p in cliente.prestamos]
        }
        resultados_busqueda.append(cliente_data)

    return jsonify(resultados_busqueda), 200


@app.route('/api/prestamos/historial/<int:cliente_id>', methods=['GET'])
@jwt_required()
def api_historial_prestamos(cliente_id):
    """Obtiene el historial completo de préstamos de un cliente específico."""
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    cliente = Cliente.query.get_or_404(cliente_id)
    prestamos = Prestamo.query.filter_by(cliente_id=cliente_id).all()
    
    return jsonify([p.to_dict() for p in prestamos]), 200


@app.route('/api/clientes/<int:id>', methods=['PUT'])
@jwt_required()
def api_update_cliente(id):
    """Actualiza la información de un cliente existente."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403
    
    cliente = Cliente.query.get_or_404(id)
    data = request.get_json() or {}
    
    cliente.nombre = data.get('nombre', cliente.nombre)
    cliente.direccion = data.get('direccion', cliente.direccion)
    cliente.telefono = data.get('telefono', cliente.telefono)
    
    db.session.commit()
    return jsonify(cliente.to_dict()), 200


@app.route('/api/clientes/<int:cliente_id>', methods=['DELETE'])
@jwt_required()
def eliminar_cliente(cliente_id):
    """Elimina un cliente y todos sus préstamos asociados."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        return jsonify({'msg': 'Cliente no encontrado'}), 404

    try:
        # Eliminar cuotas y pagos asociados a los préstamos del cliente
        prestamos_del_cliente = Prestamo.query.filter_by(cliente_id=cliente_id).all()
        for prestamo in prestamos_del_cliente:
            Cuota.query.filter_by(prestamo_id=prestamo.id).delete()
            Pago.query.filter_by(prestamo_id=prestamo.id).delete()
            db.session.delete(prestamo)

        db.session.delete(cliente)
        db.session.commit()
        return jsonify({'msg': 'Cliente eliminado correctamente'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al eliminar cliente', 'error': str(e)}), 500


@app.route('/api/trabajadores', methods=['GET'])
@jwt_required()
def api_trabajadores():
    """Obtiene la lista de todos los trabajadores (solo para administradores)."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    trabajadores = Usuario.query.filter_by(rol='trabajador').all()
    return jsonify([
        {
            'id': t.id,
            'username': t.username,
            'rol': t.rol,
            'dni': t.dni,
            'telefono': t.telefono
        } for t in trabajadores
    ]), 200


@app.route('/api/trabajadores', methods=['POST'])
@jwt_required()
def api_crear_trabajador():
    """Crea un nuevo usuario con rol de 'trabajador'."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    dni = data.get('dni')
    telefono = data.get('telefono')

    if not username or not password:
        return jsonify({'msg': 'Faltan campos'}), 400
    if Usuario.query.filter_by(username=username).first():
        return jsonify({'msg': 'Usuario ya existe'}), 400

    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    trabajador = Usuario(username=username, password_hash=pw_hash, rol='trabajador', dni=dni, telefono=telefono)
    db.session.add(trabajador)
    db.session.commit()

    return jsonify({
        'id': trabajador.id, 
        'username': trabajador.username, 
        'rol': trabajador.rol, 
        'dni': trabajador.dni,
        'telefono': trabajador.telefono
    }), 201


@app.route('/api/trabajadores/<int:id>', methods=['PUT'])
@jwt_required()
def api_editar_trabajador(id):
    """Edita la información de un trabajador existente."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    trabajador = Usuario.query.get_or_404(id)
    data = request.get_json() or {}

    trabajador.username = data.get('username', trabajador.username)
    trabajador.dni = data.get('dni', trabajador.dni)
    trabajador.telefono = data.get('telefono', trabajador.telefono)

    nueva_password = data.get('password')
    if nueva_password:
        trabajador.password_hash = bcrypt.generate_password_hash(nueva_password).decode('utf-8')

    db.session.commit()
    return jsonify({
        'id': trabajador.id,
        'username': trabajador.username,
        'rol': trabajador.rol,
        'dni': trabajador.dni,
        'telefono': trabajador.telefono
    }), 200


@app.route('/api/trabajadores/<int:id>', methods=['DELETE'])
@jwt_required()
def api_eliminar_trabajador(id):
    """Elimina un trabajador."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    trabajador = Usuario.query.get_or_404(id)
    db.session.delete(trabajador)
    db.session.commit()

    return jsonify({'msg': 'Trabajador eliminado con éxito'}), 200


@app.route('/api/resumen_creditos', methods=['GET'])
@jwt_required()
def resumen_creditos():
    """
    Proporciona un resumen estadístico de los créditos.
    Actualiza automáticamente antes de calcular.
    """
    # Actualizar todos los préstamos activos
    actualizar_prestamos_activos()
    
    total_creditos = Prestamo.query.count()
    creditos_activos = Prestamo.query.filter_by(estado='activo').count()
    creditos_vencidos = Prestamo.query.filter(
        Prestamo.estado == 'activo',
        Prestamo.fecha_fin < date.today()
    ).count()

    deuda_total = db.session.query(func.sum(Prestamo.saldo)).filter_by(estado='activo').scalar()
    if deuda_total is None:
        deuda_total = 0.0

    return jsonify({
        'totalCreditos': total_creditos,
        'creditosVigentes': creditos_activos - creditos_vencidos,
        'creditosVencidos': creditos_vencidos,
        'deudaTotal': float(deuda_total)
    })


@app.route('/api/prestamos/<int:prestamo_id>/cuotas', methods=['GET'])
@jwt_required()
def obtener_cuotas_prestamo(prestamo_id):
    """Obtiene todas las cuotas de un préstamo específico."""
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    prestamo = Prestamo.query.get_or_404(prestamo_id)
    cuotas = Cuota.query.filter_by(prestamo_id=prestamo_id).order_by(Cuota.fecha_pago.desc()).all()
    
    return jsonify({
        'prestamo_id': prestamo_id,
        'cuotas': [c.to_dict() for c in cuotas],
        'total_cuotas': len(cuotas),
        'total_pagado': sum(float(c.monto) for c in cuotas)
    }), 200


@app.route('/api/actualizar_prestamos', methods=['POST'])
@jwt_required()
def api_actualizar_prestamos():
    """Endpoint manual para actualizar días transcurridos y deuda vencida."""
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    try:
        actualizar_prestamos_activos()
        return jsonify({'msg': 'Préstamos actualizados correctamente'}), 200
    except Exception as e:
        return jsonify({'msg': 'Error al actualizar préstamos', 'error': str(e)}), 500


# ---------------- PÁGINAS HTML ----------------
@app.route('/')
def login_page():
    """Página de inicio de sesión, redirige si ya está autenticado."""
    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt()
        if claims:
            if claims.get("rol") == "admin":
                return redirect(url_for('admin_page'))
            elif claims.get("rol") == "trabajador":
                return redirect(url_for('trabajador_page'))
        return render_template('login.html')
    except:
        return render_template('login.html')


@app.route('/admin')
def admin_page():
    """Página de administración, requiere rol de 'admin'."""
    try:
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get('rol') != 'admin':
            return redirect(url_for('trabajador_page'))
        return render_template('admin.html')
    except Exception:
        return redirect(url_for('login_page'))


@app.route('/trabajador')
def trabajador_page():
    """Página de trabajador, requiere rol de 'trabajador'."""
    try:
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get('rol') not in ['trabajador']:
            return redirect(url_for('login_page'))
        return render_template('trabajador.html')
    except Exception:
        return redirect(url_for('login_page'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)