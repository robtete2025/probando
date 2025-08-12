from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token
from app.db import get_session_for_role
from app.models import Usuario
import datetime

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    # Solo por ejemplo: crea un usuario (esto idealmente lo hace solo admin)
    data = request.json
    # aquí nos conectamos con la sesión admin para poder crear usuarios
    session = get_session_for_role("admin")
    try:
        hashed = generate_password_hash(data["password"])
        u = Usuario(nombre_usuario=data["username"], clave_hash=hashed, nombre_completo=data.get("nombre"), rol=data.get("rol","trabajador"))
        session.add(u)
        session.commit()
        return jsonify({"msg":"Usuario creado"}), 201
    except Exception as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    # para login necesitamos leer usuario (SELECT) -> se puede hacer con worker o admin.
    # Usamos session admin por simplicidad para permitir login de cualquiera.
    session = get_session_for_role("admin")
    try:
        u = session.query(Usuario).filter_by(nombre_usuario=data["username"]).first()
        if not u:
            return jsonify({"error":"Credenciales inválidas"}), 401
        if not check_password_hash(u.clave_hash, data["password"]):
            return jsonify({"error":"Credenciales inválidas"}), 401
        # payload en token: id y rol
        token = create_access_token(identity={"id": u.id_usuario, "rol": u.rol}, expires_delta=datetime.timedelta(hours=8))
        return jsonify({"access_token": token})
    finally:
        session.close()
