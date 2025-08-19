from flask import Flask, render_template, redirect, url_for, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies,
    verify_jwt_in_request, get_jwt, get_jwt_identity, jwt_required
)
from datetime import timedelta, datetime, timezone, date
import os
from sqlalchemy import func, or_, and_
from decimal import Decimal
import pytz

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

# Configuración de JWT en cookies
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'prestamo123')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

# Configuración de zona horaria
TIMEZONE = pytz.timezone('America/Lima')  # Perú

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)


def get_current_date():
    """Obtiene la fecha actual en la zona horaria local"""
    return datetime.now(TIMEZONE).date()


def get_current_datetime():
    """Obtiene la fecha y hora actual en la zona horaria local"""
    return datetime.now(TIMEZONE)


# ---------------- MODELOS ----------------
class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    rol = db.Column(db.String(20), nullable=False)
    dni = db.Column(db.String(15), unique=True, nullable=True)
    telefono = db.Column(db.String(20), nullable=True)
    nombre = db.Column(db.String(100), nullable=True)  # Nuevo campo


class Cliente(db.Model):
    __tablename__ = 'clientes'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    dni = db.Column(db.String(15), unique=True, nullable=False)
    direccion = db.Column(db.Text)
    telefono = db.Column(db.String(20))
    fecha_registro = db.Column(db.DateTime, server_default=db.func.now())
    trabajador_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=True)

    prestamos = db.relationship('Prestamo', backref=db.backref('cliente', lazy=True))
    trabajador = db.relationship('Usuario', backref=db.backref('clientes', lazy=True))

    """def tiene_prestamo_activo(self):
        Verifica si el cliente tiene al menos un préstamo activo
        return any(p.estado == 'activo' for p in self.prestamos)"""


    def tiene_prestamo_activo(self):
        """Verifica si el cliente tiene al menos un préstamo activo"""
        return any(p.estado in ['activo', 'vencido'] for p in self.prestamos)

    def to_dict(self):
        return {
            'id': self.id,
            'nombre': self.nombre,
            'dni': self.dni,
            'direccion': self.direccion,
            'telefono': self.telefono,
            'fecha_registro': self.fecha_registro.isoformat() if self.fecha_registro else None,
            'prestamos': [p.to_dict() for p in self.prestamos],
            'tiene_prestamo_activo': self.tiene_prestamo_activo(),
            'trabajador_id': self.trabajador_id,
            'trabajador_nombre': self.trabajador.nombre if self.trabajador else None
        }


class Prestamo(db.Model):
    __tablename__ = 'prestamos'
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id', ondelete='CASCADE'), nullable=False)
    monto_principal = db.Column(db.Numeric(10, 2), nullable=False)
    interes = db.Column(db.Numeric(5, 2), nullable=False)
    monto_total = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date)
    fecha_pago_completo = db.Column(db.Date, nullable=True)  # Fecha cuando se completó el pago
    estado = db.Column(db.String(50), nullable=False, server_default='activo')  # activo, pagado, refinanciado, vencido
    
    # Campos de control del préstamo
    saldo = db.Column(db.Numeric(10, 2), default=0.0)
    tipo_prestamo = db.Column(db.String(10), default='CR')  # CR, REF
    tipo_frecuencia = db.Column(db.String(50), nullable=True)
    dt = db.Column(db.Integer, default=0)
    cuota_diaria = db.Column(db.Numeric(10, 2), default=0.0)
    deuda_vencida = db.Column(db.Numeric(10, 2), default=0.0)
    prestamo_refinanciado_id = db.Column(db.Integer, db.ForeignKey('prestamos.id'), nullable=True)
    cuotas = db.relationship('Cuota', backref=db.backref('prestamo', lazy=True))

    def calcular_dias_transcurridos(self):
        """Calcula días transcurridos desde el inicio usando zona horaria local"""
        if self.fecha_inicio:
            hoy = get_current_date()
            self.dt = (hoy - self.fecha_inicio).days
        return self.dt
    #BORRAR SI SALE MAL
    def calcular_deuda_vencida(self):
        """
        Calcula la deuda vencida y la mora pendiente dinámicamente.
        Devuelve deuda_vencida, deuda_vencida_base, mora_pendiente.
        """
        if self.estado not in ['activo', 'vencido']:
            self.deuda_vencida = Decimal('0.0')
            self.saldo = Decimal('0.0')
            return 0.0, 0.0, 0.0

        hoy = get_current_date()
        fecha_fin = self.fecha_fin or (self.fecha_inicio + timedelta(days=30))
        dias_transcurridos = calcular_dias_habiles(self.fecha_inicio, min(hoy, fecha_fin))

        # Calcular deuda esperada sin mora
        deuda_esperada = Decimal(str(dias_transcurridos)) * self.cuota_diaria
        total_pagado = sum(Decimal(str(cuota.monto)) for cuota in self.cuotas)
        deuda_vencida_base = max(Decimal('0.0'), deuda_esperada - total_pagado)

        # Calcular mora si el préstamo está vencido
        mora_total = Decimal('0.0')
        if hoy > fecha_fin and self.saldo > 0:
            dias_vencidos = calcular_dias_habiles(fecha_fin, hoy)  # Usar días hábiles para consistencia
            mora_diaria = Decimal('0.005') * self.monto_total
            mora_total = mora_diaria * Decimal(str(max(0, dias_vencidos)))

        # Calcular mora pendiente
        mora_pendiente = max(Decimal('0.0'), mora_total - (total_pagado - deuda_esperada if total_pagado > deuda_esperada else Decimal('0.0')))
        self.deuda_vencida = deuda_vencida_base + mora_pendiente
        self.saldo = self.monto_total - total_pagado + mora_total

        # Actualizar estado
        if hoy > fecha_fin and self.saldo > 0:
            self.estado = 'vencido'
        elif self.estado == 'vencido' and self.saldo <= 0:
            self.estado = 'pagado'
            self.fecha_pago_completo = get_current_date()

        return float(self.deuda_vencida), float(deuda_vencida_base), float(mora_pendiente)

    def calcular_estado_pago_cuota(self, fecha_cuota):
        """
        Determina si una cuota fue pagada a tiempo, anticipada o con retraso
        """
        if not self.fecha_inicio:
            return 'desconocido'
        
        dias_desde_inicio = (fecha_cuota - self.fecha_inicio).days
        
        if dias_desde_inicio < 0:
            return 'anticipado'
        elif dias_desde_inicio == 0:
            return 'a_tiempo'
        else:
            # Verificar si pagó la cuota completa del día correspondiente
            cuotas_hasta_fecha = [c for c in self.cuotas if c.fecha_pago <= fecha_cuota]
            total_pagado_hasta_fecha = sum(Decimal(str(c.monto)) for c in cuotas_hasta_fecha)
            esperado_hasta_fecha = Decimal(str(dias_desde_inicio + 1)) * self.cuota_diaria
            
            if total_pagado_hasta_fecha >= esperado_hasta_fecha:
                return 'a_tiempo'
            else:
                return 'con_retraso'
        
    def calcular_gastos_administrativos(self):
        """Calcula los gastos administrativos: 1 sol por cada 50 soles de monto principal, mínimo 1 sol."""
        monto_principal = Decimal(str(self.monto_principal))
        interes = Decimal(str(self.interes))
        # Solo calcular gastos administrativos si el interés es 10%
        if interes != Decimal('10.0'):
            return Decimal('0.0')
        if monto_principal <= 0:
            return Decimal('0.0')  # Mínimo 1 sol
        gastos = Decimal('0.0') + (monto_principal // 50) * Decimal('1.0')
        return gastos
    
    

    def to_dict(self):
        self.calcular_dias_transcurridos()
        deuda_vencida, deuda_vencida_base, mora_pendiente = self.calcular_deuda_vencida()
        
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'monto_principal': float(self.monto_principal),
            'monto_total': float(self.monto_total),
            'interes': float(self.interes),
            'fecha_inicio': self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            'fecha_fin': self.fecha_fin.isoformat() if self.fecha_fin else None,
            'fecha_pago_completo': self.fecha_pago_completo.isoformat() if self.fecha_pago_completo else None,
            'estado': self.estado,
            'saldo': float(self.saldo),
            'mora_pendiente': float(mora_pendiente),
            'tipo_prestamo': self.tipo_prestamo,
            'tipo_frecuencia': self.tipo_frecuencia,
            'dt': self.dt,
            'cuota_diaria': float(self.cuota_diaria),
            'deuda_vencida': float(self.deuda_vencida),
            'prestamo_refinanciado_id': self.prestamo_refinanciado_id,
            'total_cuotas': len(self.cuotas),
            'cuotas': [c.to_dict() for c in self.cuotas],
            'gastos_administrativos': float(self.calcular_gastos_administrativos())
        }


class Cuota(db.Model):
    __tablename__ = 'cuotas'
    id = db.Column(db.Integer, primary_key=True)
    prestamo_id = db.Column(db.Integer, db.ForeignKey('prestamos.id', ondelete='CASCADE'), nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_pago = db.Column(db.Date, nullable=False, server_default=db.func.current_date())
    descripcion = db.Column(db.String(200), nullable=True)
    estado_pago = db.Column(db.String(20), default='a_tiempo')  # a_tiempo, con_retraso, anticipado

    def to_dict(self):
        return {
            'id': self.id,
            'prestamo_id': self.prestamo_id,
            'monto': float(self.monto),
            'fecha_pago': self.fecha_pago.isoformat() if self.fecha_pago else None,
            'descripcion': self.descripcion,
            'estado_pago': self.estado_pago
        }


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


# ---------------- AUTENTICACIÓN ----------------
@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({'msg': 'Faltan campos'}), 400

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
    rol = get_jwt().get('rol')
    return jsonify({'rol': rol}), 200


@app.route('/auth/logout', methods=['POST'])
def logout():
    resp = jsonify({'msg': 'logout'})
    unset_jwt_cookies(resp)
    return resp, 200


@jwt_required(optional=True)
@app.after_request
def refresh_expiring_jwts(response):
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
    monto_principal = Decimal(str(monto_principal))
    interes = Decimal(str(interes))
    interes_monto = monto_principal * (interes / 100)
    return monto_principal + interes_monto


def calcular_fecha_fin(fecha_inicio, tipo_frecuencia, monto_total, cuota_diaria):
    """monto_total = Decimal(str(monto_total))
    cuota_diaria = Decimal(str(cuota_diaria))
    
    if cuota_diaria <= 0:
        return fecha_inicio + timedelta(days=30)
    
    dias_necesarios = int(monto_total / cuota_diaria)
    if monto_total % cuota_diaria > 0:
        dias_necesarios += 1
    
    fecha_fin = fecha_inicio + timedelta(days=dias_necesarios)"""
    fecha_fin = fecha_inicio + timedelta(days=30)
    return fecha_fin

def calcular_dias_habiles(fecha_inicio, fecha_fin):
    """Calcula los días hábiles (lunes a viernes) entre dos fechas, hasta un máximo de 22 días."""
    dias = 0
    current_date = fecha_inicio
    while current_date <= fecha_fin and dias < 22:
        if current_date.weekday() < 6:  # Lunes a viernes (0 a 4)
            dias += 1
        current_date += timedelta(days=1)
    return dias

def actualizar_prestamos_activos():
    """Actualiza días transcurridos y deuda vencida para todos los préstamos activos"""
    prestamos_activos = Prestamo.query.filter(Prestamo.estado.in_(['activo', 'vencido'])).all()
    
    for prestamo in prestamos_activos:
        prestamo.calcular_dias_transcurridos()
        prestamo.calcular_deuda_vencida()
    
    db.session.commit()


# ---------------- API ENDPOINTS ----------------

@app.route('/api/usuario', methods=['GET'])
@jwt_required()
def obtener_usuario():
    try:
        username = get_jwt_identity()
        usuario = Usuario.query.filter_by(username=username).first()
        
        if not usuario:
            return jsonify({'msg': 'Usuario no encontrado'}), 404
        
        return jsonify({
            'username': usuario.username,
            'nombre': usuario.nombre or usuario.username,  # Usa nombre si existe, sino username
            'rol': usuario.rol,
            'dni': usuario.dni,
            'telefono': usuario.telefono
        }), 200
    except Exception as e:
        print(f"Error obteniendo usuario: {e}")
        return jsonify({'msg': 'Error al obtener datos del usuario'}), 500

@app.route('/api/clientes_con_prestamo', methods=['POST'])
@jwt_required()
def crear_cliente_con_prestamo():
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    data = request.get_json() or {}
    cliente_data = data.get('cliente', {})
    nombre = cliente_data.get('nombre')
    dni = cliente_data.get('dni')
    telefono = cliente_data.get('telefono')
    direccion = cliente_data.get('direccion')
    trabajador_id = cliente_data.get('trabajador_id')

    if not nombre or not dni:
        return jsonify({'msg': 'Faltan campos de cliente'}), 400
    if Cliente.query.filter_by(dni=dni).first():
        return jsonify({'msg': 'Cliente con ese DNI ya existe'}), 400
    if trabajador_id and not Usuario.query.filter_by(id=trabajador_id, rol='trabajador').first():
        return jsonify({'msg': 'Trabajador no válido'}), 400

    prestamo_data = data.get('prestamo', {})
    monto_principal = prestamo_data.get('monto')
    interes = prestamo_data.get('interes')
    fecha_inicio_str = prestamo_data.get('fecha_inicio')
    tipo_frecuencia = prestamo_data.get('tipo_frecuencia', 'Diario')
    #cuota_diaria = prestamo_data.get('cuota')

    if not monto_principal or not interes or not fecha_inicio_str:
        return jsonify({'msg': 'Faltan campos de préstamo'}), 400

    try:
        monto_principal = Decimal(str(monto_principal))
        interes = Decimal(str(interes))
        fecha_inicio = datetime.fromisoformat(fecha_inicio_str).date()
        # Calcular monto_total primero
        monto_total = calcular_monto_total(monto_principal, interes)
        # Luego calcular cuota_diaria
        cuota_diaria = monto_total / Decimal('22')  # Cuota diaria para 22 días
        fecha_fin = calcular_fecha_fin(fecha_inicio, tipo_frecuencia, monto_total, cuota_diaria)

        nuevo_cliente = Cliente(
            nombre=nombre,
            dni=dni,
            telefono=telefono,
            direccion=direccion,
            trabajador_id=trabajador_id 
        )
        db.session.add(nuevo_cliente)
        db.session.flush()

        nuevo_prestamo = Prestamo(
            cliente_id=nuevo_cliente.id,
            monto_principal=monto_principal,
            interes=interes,
            monto_total=monto_total,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            saldo=monto_total,
            tipo_prestamo='CR',
            tipo_frecuencia=tipo_frecuencia,
            cuota_diaria=cuota_diaria,
            dt=0
        )
        db.session.add(nuevo_prestamo)
        db.session.commit()

        return jsonify({'msg': 'Cliente y préstamo creados', 'cliente': nuevo_cliente.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al refinanciar el préstamo', 'error': str(e)}), 500


@app.route('/api/prestamos/<int:prestamo_id>/pagado_manual', methods=['PUT'])
@jwt_required()
def marcar_prestamo_pagado(prestamo_id):
    try:
        claims = get_jwt()
        if claims.get('rol') != 'admin':
            return jsonify({'msg': 'No autorizado'}), 403

        prestamo = db.session.get(Prestamo, prestamo_id)
        if not prestamo:
            return jsonify({'msg': 'Préstamo no encontrado'}), 404

        prestamo.estado = 'pagado'
        prestamo.saldo = Decimal('0.0')
        prestamo.deuda_vencida = Decimal('0.0')
        prestamo.fecha_pago_completo = get_current_date()
        
        if prestamo.tipo_prestamo == 'REF' and prestamo.prestamo_refinanciado_id:
            prestamo_original = db.session.get(Prestamo, prestamo.prestamo_refinanciado_id)
            if prestamo_original:
                prestamo_original.estado = 'pagado'
                prestamo_original.saldo = Decimal('0.0')
                prestamo_original.deuda_vencida = Decimal('0.0')
                prestamo_original.fecha_pago_completo = get_current_date()

        db.session.commit()
        return jsonify({'msg': 'Préstamo marcado como pagado exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al marcar el préstamo como pagado', 'error': str(e)}), 500


@app.route('/api/prestamos', methods=['POST'])
@jwt_required()
def api_create_prestamo():
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403
    
    data = request.get_json() or {}
    required = ['cliente_id', 'monto', 'interes', 'fecha_inicio']
    if not all(k in data for k in required):
        return jsonify({'msg': 'Faltan campos requeridos'}), 400
    
    cliente = db.session.get(Cliente, data['cliente_id'])
    if not cliente:
        return jsonify({'msg': 'Cliente no existe'}), 404
    
    # Verificar que el cliente no tenga préstamos activos
    if cliente.tiene_prestamo_activo():
        return jsonify({'msg': 'El cliente ya tiene un préstamo activo'}), 400

    try:
        fecha_inicio = datetime.fromisoformat(data['fecha_inicio']).date()
        tipo_frecuencia = data.get('tipo_frecuencia', 'Diario')
        monto_principal = Decimal(str(data['monto']))
        interes = Decimal(str(data['interes']))
        monto_total = calcular_monto_total(monto_principal, interes)
        cuota_diaria = monto_total / Decimal('22')  # Calcular cuota_diaria para 22 días
        fecha_fin = calcular_fecha_fin(fecha_inicio, tipo_frecuencia, monto_total, cuota_diaria)

        p = Prestamo(
            cliente_id=data['cliente_id'],
            monto_principal=monto_principal,
            interes=interes,
            monto_total=monto_total,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            estado='activo',
            saldo=monto_total,
            tipo_prestamo='CR',
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
            'telefono': t.telefono,
            'nombre': t.nombre  # Incluir nombre en la respuesta
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
    nombre = data.get('nombre')  # Nuevo campo

    if not username or not password or not nombre:
        return jsonify({'msg': 'Faltan campos'}), 400
    if Usuario.query.filter_by(username=username).first():
        return jsonify({'msg': 'Usuario ya existe'}), 400
    if Usuario.query.filter_by(dni=dni).first():
        return jsonify({'msg': 'DNI ya registrado'}), 400

    pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    trabajador = Usuario(
        username=username, 
        password_hash=pw_hash, 
        rol='trabajador', 
        dni=dni, 
        telefono=telefono,
        nombre=nombre  # Asignar nombre
    )
    db.session.add(trabajador)
    db.session.commit()

    return jsonify({
        'id': trabajador.id, 
        'username': trabajador.username, 
        'rol': trabajador.rol, 
        'dni': trabajador.dni,
        'telefono': trabajador.telefono,
        'nombre': trabajador.nombre  # Incluir nombre en la respuesta
    }), 201


@app.route('/api/trabajadores/<int:id>', methods=['PUT'])
@jwt_required()
def api_editar_trabajador(id):
    """Edita la información de un trabajador existente."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    trabajador = db.session.get(Usuario, id)
    if not trabajador:
        return jsonify({'msg': 'Trabajador no encontrado'}), 404
    data = request.get_json() or {}

    trabajador.username = data.get('username', trabajador.username)
    trabajador.dni = data.get('dni', trabajador.dni)
    trabajador.telefono = data.get('telefono', trabajador.telefono)
    trabajador.nombre = data.get('nombre', trabajador.nombre)  # Actualizar nombre

    nueva_password = data.get('password')
    if nueva_password:
        trabajador.password_hash = bcrypt.generate_password_hash(nueva_password).decode('utf-8')

    db.session.commit()
    return jsonify({
        'id': trabajador.id,
        'username': trabajador.username,
        'rol': trabajador.rol,
        'dni': trabajador.dni,
        'telefono': trabajador.telefono,
        'nombre': trabajador.nombre  # Incluir nombre en la respuesta
    }), 200


@app.route('/api/trabajadores/<int:id>', methods=['DELETE'])
@jwt_required()
def api_eliminar_trabajador(id):
    """Elimina un trabajador."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    trabajador = db.session.get(Usuario, id)
    if not trabajador:
        return jsonify({'msg': 'Trabajador no encontrado'}), 404
    db.session.delete(trabajador)
    db.session.commit()

    return jsonify({'msg': 'Trabajador eliminado con éxito'}), 200


@app.route('/api/resumen_creditos', methods=['GET'])
@jwt_required()
def resumen_creditos():
    """
    Proporciona un resumen estadístico mejorado de los créditos.
    """
    actualizar_prestamos_activos()
    
    # Conteos básicos
    total_creditos = Prestamo.query.count()
    creditos_activos = Prestamo.query.filter_by(estado='activo').count()
    creditos_vencidos = Prestamo.query.filter_by(estado='vencido').count()
    creditos_pagados = Prestamo.query.filter_by(estado='pagado').count()
    creditos_refinanciados = Prestamo.query.filter_by(estado='refinanciado').count()

    # Créditos vigentes = activos (no vencidos)
    creditos_vigentes = creditos_activos

    # Deuda total (solo préstamos activos y vencidos)
    deuda_total = db.session.query(func.sum(Prestamo.saldo)).filter(
        Prestamo.estado.in_(['activo', 'vencido'])
    ).scalar()
    if deuda_total is None:
        deuda_total = 0.0

    # Deuda vencida total
    deuda_vencida_total = db.session.query(func.sum(Prestamo.deuda_vencida)).filter(
        Prestamo.estado.in_(['activo', 'vencido'])
    ).scalar()
    if deuda_vencida_total is None:
        deuda_vencida_total = 0.0

    # Total de gastos administrativos (solo préstamos activos y vencidos)
    gastos_administrativos_total = sum(
        prestamo.calcular_gastos_administrativos() 
        for prestamo in Prestamo.query.all() 
    )

    return jsonify({
        'totalCreditos': total_creditos,
        'creditosVigentes': creditos_vigentes,
        'creditosVencidos': creditos_vencidos,
        'creditosPagados': creditos_pagados,
        'creditosRefinanciados': creditos_refinanciados,
        'deudaTotal': float(deuda_total),
        'deudaVencidaTotal': float(deuda_vencida_total),
        'gastosAdministrativosTotal': float(gastos_administrativos_total)  # Nuevo campo
    })


@app.route('/api/prestamos/<int:prestamo_id>/cuotas', methods=['GET'])
@jwt_required()
def obtener_cuotas_prestamo(prestamo_id):
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    prestamo = Prestamo.query.get_or_404(prestamo_id)
    cuotas = Cuota.query.filter_by(prestamo_id=prestamo_id).order_by(Cuota.fecha_pago.desc()).all()
    
    # Calcular deuda vencida y mora
    deuda_vencida, deuda_vencida_base, mora_pendiente = prestamo.calcular_deuda_vencida()
    
    return jsonify({
        'prestamo_id': prestamo_id,
        'prestamo_info': {
            'cliente_nombre': prestamo.cliente.nombre,
            'monto_total': float(prestamo.monto_total),
            'saldo_actual': float(prestamo.saldo),
            'mora_total': float(mora_pendiente),
            'estado': prestamo.estado
        },
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


# Mantener compatibilidad
@app.route('/api/prestamos/<int:prestamo_id>/pagar', methods=['POST'])
@jwt_required()
def api_pagar_prestamo(prestamo_id):
    return registrar_cuota(prestamo_id)


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
        if claims.get('rol') not in ['trabajador', 'admin']:
            return redirect(url_for('login_page'))
        return render_template('trabajador.html')
    except Exception:
        return redirect(url_for('login_page'))

@app.route('/api/clientes', methods=['GET'])
@jwt_required()
def api_clientes():
    actualizar_prestamos_activos()
    
    clientes_bd = Cliente.query.all()
    clientes_con_prestamos_activos = []

    for cliente in clientes_bd:
        prestamos_activos = [p for p in cliente.prestamos if p.estado in ['activo', 'vencido']]

        if prestamos_activos:
            cliente_data = {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'dni': cliente.dni,
                'direccion': cliente.direccion,
                'telefono': cliente.telefono,
                'fecha_registro': cliente.fecha_registro.isoformat() if cliente.fecha_registro else None,
                'prestamos': [p.to_dict() for p in prestamos_activos],
                'tiene_prestamo_activo': cliente.tiene_prestamo_activo(),
                'trabajador_id': cliente.trabajador_id,
                'trabajador_nombre': (
                    cliente.trabajador.nombre if cliente.trabajador and cliente.trabajador.nombre 
                    else cliente.trabajador.username if cliente.trabajador 
                    else 'No asignado'
                )
            }
            clientes_con_prestamos_activos.append(cliente_data)

    return jsonify(clientes_con_prestamos_activos), 200


@app.route('/api/clientes_sin_prestamo', methods=['GET'])
@jwt_required()
def api_clientes_sin_prestamo():
    """Obtiene clientes que no tienen préstamos activos para poder crear nuevos préstamos"""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    clientes_bd = Cliente.query.all()
    clientes_sin_prestamo_activo = []

    for cliente in clientes_bd:
        if not cliente.tiene_prestamo_activo():
            clientes_sin_prestamo_activo.append({
                'id': cliente.id,
                'nombre': cliente.nombre,
                'dni': cliente.dni,
                'direccion': cliente.direccion,
                'telefono': cliente.telefono
            })

    return jsonify(clientes_sin_prestamo_activo), 200


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
        # Actualizar todos los préstamos del cliente
        for prestamo in cliente.prestamos:
            prestamo.calcular_dias_transcurridos()
            prestamo.calcular_deuda_vencida()
        
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

    db.session.commit()  # Guardar actualizaciones
    return jsonify(resultados_busqueda), 200


@app.route('/api/prestamos/historial/<int:cliente_id>', methods=['GET'])
@jwt_required()
def api_historial_prestamos(cliente_id):
    """Obtiene el historial completo de préstamos de un cliente específico."""
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    cliente = db.session.get(Cliente, cliente_id)
    if not cliente:
        return jsonify({'msg': 'Cliente no encontrado'}), 404
    prestamos = Prestamo.query.filter_by(cliente_id=cliente_id).order_by(Prestamo.fecha_inicio.desc()).all()
    
    # Actualizar información de préstamos
    for prestamo in prestamos:
        prestamo.calcular_dias_transcurridos()
        prestamo.calcular_deuda_vencida()
    
    db.session.commit()
    return jsonify([p.to_dict() for p in prestamos]), 200


@app.route('/api/clientes/<int:id>', methods=['PUT'])
@jwt_required()
def api_update_cliente(id):
    """Actualiza la información de un cliente existente."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403
    
    cliente = db.session.get(Cliente, id)
    if not cliente:
        return jsonify({'msg': 'Cliente no encontrado'}), 404
    data = request.get_json() or {}
    
    cliente.nombre = data.get('nombre', cliente.nombre)
    cliente.direccion = data.get('direccion', cliente.direccion)
    cliente.telefono = data.get('telefono', cliente.telefono)
    trabajador_id = data.get('trabajador_id')
    if trabajador_id is not None:
        if trabajador_id and not Usuario.query.filter_by(id=trabajador_id, rol='trabajador').first():
            return jsonify({'msg': 'Trabajador no válido'}), 400
        cliente.trabajador_id = trabajador_id
        
    db.session.commit()
    return jsonify(cliente.to_dict()), 200


@app.route('/api/clientes/<int:cliente_id>', methods=['DELETE'])
@jwt_required()
def eliminar_cliente(cliente_id):
    """Elimina un cliente y todos sus préstamos asociados."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    cliente = db.session.get(Cliente, cliente_id)
    if not cliente:
        return jsonify({'msg': 'Cliente no encontrado'}), 404

    try:
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


@app.route('/api/prestamos/<int:prestamo_id>/cuota', methods=['POST'])
@jwt_required()
def registrar_cuota(prestamo_id):
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    prestamo = db.session.get(Prestamo, prestamo_id)
    if not prestamo:
        return jsonify({'msg': 'Préstamo no encontrado'}), 404
    data = request.get_json() or {}
    monto_cuota = data.get('monto')

    if not monto_cuota or float(monto_cuota) <= 0:
        return jsonify({'msg': 'Monto de cuota inválido'}), 400

    try:
        monto_cuota = Decimal(str(monto_cuota))
        prestamo.calcular_dias_transcurridos()
        hoy = get_current_date()
        fecha_fin = prestamo.fecha_fin or (prestamo.fecha_inicio + timedelta(days=30))
        
        # Calcular deuda vencida y mora antes del pago
        deuda_vencida, deuda_vencida_base, mora_pendiente = prestamo.calcular_deuda_vencida()

        if prestamo.saldo <= 0:
            return jsonify({'msg': 'El préstamo ya está completamente pagado'}), 400

        # Distribuir el pago: primero a la deuda base, luego a la mora
        monto_a_deuda_base = min(monto_cuota, Decimal(str(deuda_vencida_base)))
        monto_a_mora = min(monto_cuota - monto_a_deuda_base, Decimal(str(mora_pendiente)))
        monto_real_cuota = monto_a_deuda_base + monto_a_mora

        # Actualizar saldo
        saldo_completado = False
        if prestamo.saldo <= monto_real_cuota:
            monto_real_cuota = prestamo.saldo
            prestamo.saldo = Decimal('0.0')
            prestamo.estado = 'pagado'
            prestamo.fecha_pago_completo = get_current_date()
            saldo_completado = True
        else:
            prestamo.saldo -= monto_real_cuota

        # Registrar la cuota
        fecha_pago = get_current_date()
        estado_pago = prestamo.calcular_estado_pago_cuota(fecha_pago)
        nueva_cuota = Cuota(
            prestamo_id=prestamo_id,
            monto=monto_real_cuota,
            fecha_pago=fecha_pago,
            descripcion=f'Cuota diaria (deuda: {monto_a_deuda_base}, mora: {monto_a_mora})',
            estado_pago=estado_pago
        )
        db.session.add(nueva_cuota)
        
        # Recalcular deuda vencida
        deuda_vencida, deuda_vencida_base, mora_pendiente = prestamo.calcular_deuda_vencida()
        db.session.commit()

        message = f'Cuota registrada exitosamente (deuda base: {monto_a_deuda_base}, mora: {monto_a_mora})'
        if saldo_completado:
            message = '¡PRÉSTAMO PAGADO COMPLETAMENTE! La cuota ha liquidado el saldo pendiente.'

        return jsonify({
            'msg': message,
            'prestamo_completado': saldo_completado,
            'prestamo': prestamo.to_dict(),
            'cuota': nueva_cuota.to_dict(),
            'mora_pendiente': float(mora_pendiente)
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al registrar la cuota', 'error': str(e)}), 500


@app.route('/api/prestamos/<int:prestamo_id>/refinanciar', methods=['POST'])
@jwt_required()
def refinanciar_prestamo(prestamo_id):
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403

    prestamo_original = db.session.get(Prestamo, prestamo_id)
    if not prestamo_original:
        return jsonify({'msg': 'Préstamo no encontrado'}), 404
    
    if prestamo_original.estado not in ['activo', 'vencido']:
        return jsonify({'msg': 'Solo se pueden refinanciar préstamos activos o vencidos'}), 400
    
    if prestamo_original.saldo <= 0:
        return jsonify({'msg': 'El préstamo ya está pagado completamente'}), 400

    data = request.get_json() or {}
    nuevo_interes = data.get('interes')

    if not nuevo_interes:
        return jsonify({'msg': 'Falta el campo interes'}), 400

    try:
        prestamo_original.calcular_dias_transcurridos()
        prestamo_original.estado = 'refinanciado'
        
        saldo_pendiente = prestamo_original.saldo
        nuevo_monto_total = calcular_monto_total(saldo_pendiente, nuevo_interes)
        nueva_cuota_diaria = nuevo_monto_total / Decimal('22')  # Calcular cuota_diaria para 22 días
        
        fecha_inicio_refinanciacion = get_current_date()
        fecha_fin_refinanciacion = calcular_fecha_fin(
            fecha_inicio_refinanciacion, 
            prestamo_original.tipo_frecuencia, 
            nuevo_monto_total, 
            nueva_cuota_diaria
        )

        prestamo_refinanciado = Prestamo(
            cliente_id=prestamo_original.cliente_id,
            monto_principal=saldo_pendiente,
            interes=nuevo_interes,
            monto_total=nuevo_monto_total,
            fecha_inicio=fecha_inicio_refinanciacion,
            fecha_fin=fecha_fin_refinanciacion,
            saldo=nuevo_monto_total,
            tipo_prestamo='REF',
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
        return jsonify({'msg': 'Error al crear el cliente y el préstamo', 'error': str(e)}), 500
                        
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
