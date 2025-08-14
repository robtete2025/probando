from flask import Flask, render_template, redirect, url_for, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies,
    verify_jwt_in_request, get_jwt, jwt_required
)
from datetime import timedelta, datetime, timezone
import os
from sqlalchemy import func, or_

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
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=3)
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
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    interes = db.Column(db.Numeric(5, 2), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date)
    estado = db.Column(db.String(50), nullable=False, server_default='activo')

    saldo = db.Column(db.Numeric(10, 2), default=0.0)
    tipo = db.Column(db.String(50), nullable=True)
    dt = db.Column(db.Integer, default=0)
    cuota = db.Column(db.Numeric(10, 2), default=0.0)
    deuda_vencida = db.Column(db.Numeric(10, 2), default=0.0)

    pagos = db.relationship('Pago', backref=db.backref('prestamo', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'cliente_id': self.cliente_id,
            'monto': float(self.monto),
            'interes': float(self.interes),
            'fecha_inicio': self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            'fecha_fin': self.fecha_fin.isoformat() if self.fecha_fin else None,
            'estado': self.estado,
            'saldo': float(self.saldo),
            'tipo': self.tipo,
            'dt': self.dt,
            'cuota': float(self.cuota),
            'deuda_vencida': float(self.deuda_vencida)
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
    Refresca el token JWT si está a punto de expirar.
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


# ---------------- API (usa cookies -> jwt_required funciona) ----------------
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
    monto = prestamo_data.get('monto')
    interes = prestamo_data.get('interes')
    fecha_inicio_str = prestamo_data.get('fecha_inicio')

    if not monto or not interes or not fecha_inicio_str:
        return jsonify({'msg': 'Faltan campos de préstamo'}), 400

    try:
        fecha_inicio = datetime.fromisoformat(fecha_inicio_str).date()

        # Calcular DT y fecha_fin
        tipo_prestamo = prestamo_data.get('tipo', 'Diario')
        if tipo_prestamo == 'Diario':
            dias_tramo = 1
        elif tipo_prestamo == 'Semanal':
            dias_tramo = 7
        elif tipo_prestamo == 'Quincenal':
            dias_tramo = 15
        else:  # Mensual
            dias_tramo = 30

        fecha_fin = fecha_inicio + timedelta(days=dias_tramo)

        nuevo_cliente = Cliente(
            nombre=nombre,
            dni=dni,
            telefono=telefono,
            direccion=direccion
        )
        db.session.add(nuevo_cliente)
        db.session.flush()  # Para obtener el ID del cliente antes de hacer commit

        nuevo_prestamo = Prestamo(
            cliente_id=nuevo_cliente.id,
            monto=monto,
            interes=interes,
            fecha_inicio=fecha_inicio,
            saldo=monto,
            tipo=tipo_prestamo,
            cuota=prestamo_data.get('cuota'),
            dt=dias_tramo,
            fecha_fin=fecha_fin
        )
        db.session.add(nuevo_prestamo)
        db.session.commit()

        return jsonify({'msg': 'Cliente y préstamo creados', 'cliente': nuevo_cliente.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al crear el cliente y el préstamo', 'error': str(e)}), 500


# --- Endpoints de administración (requieren rol 'admin') ---
# Función auxiliar para verificar si el usuario es administrador
def es_admin():
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return False, jsonify({"msg": "Acceso denegado: Se requiere rol de administrador"}), 403
    return True, None, None

@app.route('/api/clientes', methods=['GET'])
@jwt_required()
def api_clientes():
    """
    Obtiene los clientes que tienen al menos un préstamo activo.
    """
    # Obtener todos los clientes de la base de datos
    clientes_bd = Cliente.query.all()

    clientes_con_prestamos_activos = []

    for cliente in clientes_bd:
        # Filtramos los préstamos de cada cliente para encontrar solo los activos
        # El campo 'estado' de la tabla Prestamo es el que usamos para el filtro
        prestamos_activos = [p for p in cliente.prestamos if p.estado == 'activo']

        # Si el cliente tiene al menos un préstamo activo, lo incluimos en la lista de respuesta
        if prestamos_activos:
            # Creamos un diccionario para el cliente con solo sus préstamos activos
            cliente_data = {
                'id': cliente.id,
                'nombre': cliente.nombre,
                'dni': cliente.dni,
                'direccion': cliente.direccion,
                'telefono': cliente.telefono,
                'fecha_registro': cliente.fecha_registro.isoformat() if cliente.fecha_registro else None,
                'prestamos': [p.to_dict() for p in prestamos_activos] # Solo se incluyen los préstamos activos
            }
            clientes_con_prestamos_activos.append(cliente_data)

    return jsonify(clientes_con_prestamos_activos), 200

@app.route('/api/clientes/search', methods=['GET'])
@jwt_required()
def api_search_clientes():
    """
    Busca clientes por nombre o DNI y devuelve TODOS sus préstamos.
    """
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify([]), 200
    
    # Realiza la búsqueda en la base de datos
    clientes_encontrados = Cliente.query.filter(or_(
        Cliente.nombre.ilike(f'%{search_term}%'),
        Cliente.dni.ilike(f'%{search_term}%')
    )).all()

    resultados_busqueda = []
    for cliente in clientes_encontrados:
        # Ahora se obtienen TODOS los préstamos del cliente encontrado, sin filtrar por estado.
        prestamos_del_cliente = cliente.prestamos
        cliente_data = {
            'id': cliente.id,
            'nombre': cliente.nombre,
            'dni': cliente.dni,
            'direccion': cliente.direccion,
            'telefono': cliente.telefono,
            'fecha_registro': cliente.fecha_registro.isoformat() if cliente.fecha_registro else None,
            'prestamos': [p.to_dict() for p in prestamos_del_cliente]
        }
        resultados_busqueda.append(cliente_data)

    return jsonify(resultados_busqueda), 200

# NUEVA RUTA: Buscar préstamos por cliente
@app.route('/api/historial/search', methods=['GET'])
@jwt_required()
def api_search_historial():
    """Busca clientes por nombre o DNI y devuelve TODOS sus préstamos."""
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify([]), 200

    # Busca clientes que coincidan con el término en nombre o DNI
    clientes = Cliente.query.filter(
        or_(
            Cliente.nombre.ilike(f'%{search_term}%'),
            Cliente.dni.ilike(f'%{search_term}%')
        )
    ).all()

    # Recopila todos los préstamos de los clientes encontrados
    prestamos_encontrados = []
    for cliente in clientes:
        for prestamo in cliente.prestamos:
            prestamos_encontrados.append({
                'cliente_nombre': cliente.nombre,
                'cliente_dni': cliente.dni,
                **prestamo.to_dict()
            })

    return jsonify(prestamos_encontrados), 200

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
    # Lógica para encontrar y eliminar el cliente
    cliente = Cliente.query.get(cliente_id)
    if not cliente:
        return jsonify({'msg': 'Cliente no encontrado'}), 404

    prestamos_del_cliente = Prestamo.query.filter_by(cliente_id=cliente_id).all()
    for prestamo in prestamos_del_cliente:
        db.session.delete(prestamo)

    db.session.delete(cliente)
    db.session.commit()

    return jsonify({'msg': 'Cliente eliminado correctamente'}), 200


@app.route('/api/prestamos', methods=['POST'])
@jwt_required()
def api_create_prestamo():
    """Crea un nuevo préstamo para un cliente existente."""
    claims = get_jwt()
    if claims.get('rol') != 'admin':
        return jsonify({'msg': 'No autorizado'}), 403
    data = request.get_json() or {}
    required = ['cliente_id', 'monto', 'interes', 'fecha_inicio']
    if not all(k in data for k in required):
        return jsonify({'msg': 'faltan campos'}), 400
    cliente = Cliente.query.get(data['cliente_id'])
    if not cliente:
        return jsonify({'msg': 'cliente no existe'}), 404

    fecha_inicio = datetime.fromisoformat(data['fecha_inicio']).date()
    fecha_fin = datetime.fromisoformat(data['fecha_fin']).date() if data.get('fecha_fin') else None

    p = Prestamo(
        cliente_id=data['cliente_id'],
        monto=data['monto'],
        interes=data['interes'],
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        estado=data.get('estado', 'activo'),
        saldo=data.get('monto'),
        tipo=data.get('tipo'),
        cuota=data.get('cuota')
    )
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@app.route('/api/prestamos/<int:prestamo_id>/pagar', methods=['POST'])
@jwt_required()
def api_pagar_prestamo(prestamo_id):
    """
    Ruta para registrar un pago de un préstamo.
    Permitido para roles 'admin' y 'trabajador'.
    """
    claims = get_jwt()
    if claims.get('rol') not in ['admin', 'trabajador']:
        return jsonify({'msg': 'No autorizado'}), 403

    prestamo = Prestamo.query.get_or_404(prestamo_id)
    data = request.get_json() or {}
    monto_pago = data.get('monto')

    if not monto_pago or float(monto_pago) <= 0:
        return jsonify({'msg': 'Monto de pago inválido'}), 400

    try:
        monto_pago = float(monto_pago)

        # Actualizar el saldo del préstamo
        if prestamo.saldo <= monto_pago:
            monto_real_pago = float(prestamo.saldo)
            prestamo.saldo = 0.0
            prestamo.estado = 'pagado'
        else:
            monto_real_pago = monto_pago
            prestamo.saldo -= monto_real_pago

        # Actualizar la deuda vencida (si existe)
        if prestamo.deuda_vencida > 0:
            if prestamo.deuda_vencida > monto_real_pago:
                prestamo.deuda_vencida -= monto_real_pago
            else:
                prestamo.deuda_vencida = 0.0

        # Crear el registro del pago
        nuevo_pago = Pago(
            prestamo_id=prestamo_id,
            monto=monto_real_pago,
            fecha_pago=datetime.now().date()
        )
        db.session.add(nuevo_pago)
        db.session.commit()

        return jsonify({
            'msg': 'Pago registrado exitosamente',
            'prestamo': prestamo.to_dict(),
            'pago': nuevo_pago.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al registrar el pago', 'error': str(e)}), 500


# ---- RUTA PARA MARCAR PRÉSTAMO PAGADO MANUALMENTE ----
@app.route('/api/prestamos/<int:prestamo_id>/pagado_manual', methods=['PUT'])
@jwt_required()
def marcar_prestamo_pagado(prestamo_id):
    """
    Ruta para marcar manualmente un préstamo como 'pagado'.
    Requiere el rol de 'admin' para su ejecución.
    También reinicia el saldo y la deuda vencida a 0.0.
    """
    try:
        claims = get_jwt()
        if claims.get('rol') != 'admin':
            return jsonify({'msg': 'No autorizado'}), 403

        prestamo = Prestamo.query.get(prestamo_id)
        if not prestamo:
            return jsonify({'msg': 'Préstamo no encontrado'}), 404

        # Actualiza el estado del préstamo
        prestamo.estado = 'pagado'
        # Asegura que el saldo y la deuda vencida sean 0
        prestamo.saldo = 0.0
        prestamo.deuda_vencida = 0.0
        db.session.commit()

        return jsonify({'msg': 'Préstamo marcado como pagado exitosamente'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'msg': 'Error al marcar el préstamo como pagado', 'error': str(e)}), 500


# Endpoint para obtener préstamos pagados
@app.route('/api/prestamos/pagados')
@jwt_required()
def get_prestamos_pagados():
    prestamos_pagados = db.session.query(Prestamo).filter(Prestamo.estado == 'pagado').all()
    prestamos_pagados_data = []
    for p in prestamos_pagados:
        cliente = Cliente.query.get(p.cliente_id)
        prestamos_pagados_data.append({
            **p.to_dict(),
            'nombre_cliente': cliente.nombre if cliente else 'N/A'
        })
    return jsonify(prestamos_pagados_data)

@app.route('/api/trabajadores', methods=['GET'])
@jwt_required()
def api_trabajadores():
    """Obtiene la lista de todos los trabajadores."""
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

    return jsonify({'id': trabajador.id, 'username': trabajador.username, 'rol': trabajador.rol, 'dni': trabajador.dni,
                    'telefono': trabajador.telefono}), 201


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
    Proporciona un resumen de los créditos.
    """
    total_creditos = Prestamo.query.count()
    creditos_activos = Prestamo.query.filter_by(estado='activo').count()
    creditos_vencidos = Prestamo.query.filter(
        Prestamo.estado == 'activo',
        Prestamo.fecha_fin < datetime.now().date()
    ).count()

    deuda_total = db.session.query(func.sum(Prestamo.saldo)).scalar()
    if deuda_total is None:
        deuda_total = 0.0

    return jsonify({
        'totalCreditos': total_creditos,
        'creditosVigentes': creditos_activos - creditos_vencidos,
        'creditosVencidos': creditos_vencidos,
        'deudaTotal': float(deuda_total)
    })


# ---------------- PÁGINAS HTML ----------------
@app.route('/')
def login_page():
    """Ruta de la página de inicio de sesión, redirige si ya está autenticado."""
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
