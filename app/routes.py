from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.db import get_session_for_role
from app.models import Prestamo, Cliente
from sqlalchemy.exc import SQLAlchemyError

bp = Blueprint("api", __name__)

# Todos autenticados pueden listar prestamos (trabajador o admin)
@bp.route("/prestamos", methods=["GET"])
@jwt_required()
def listar_prestamos():
    user = get_jwt_identity()
    # usar sesión worker para garantizar que no se pueda escribir desde ese usuario DB
    session = get_session_for_role("trabajador")
    try:
        rows = session.query(Prestamo).all()
        result = []
        for p in rows:
            # para mostrar cliente nombre, hacemos una consulta
            cliente = session.query(Cliente).filter_by(id_cliente=p.id_cliente).first()
            result.append({
                "id": p.id_prestamo,
                "cliente": cliente.nombre_completo if cliente else None,
                "monto_total": str(p.monto_total),
                "saldo": str(p.saldo),
                "fecha_inicio": p.fecha_inicio.isoformat()
            })
        return jsonify(result)
    finally:
        session.close()

# Solo admin puede crear préstamos
@bp.route("/prestamos", methods=["POST"])
@jwt_required()
def crear_prestamo():
    user = get_jwt_identity()
    if user["rol"] != "admin":
        return jsonify({"error":"No autorizado"}), 403

    session = get_session_for_role("admin")
    data = request.json
    try:
        nuevo = Prestamo(
            id_cliente = data["id_cliente"],
            monto_total = data["monto_total"],
            saldo = data["saldo"],
            tipo = data.get("tipo"),
            dias_transcurridos = data.get("dias_transcurridos"),
            cuotas_pagadas = data.get("cuotas_pagadas"),
            deuda_vencida = data.get("deuda_vencida"),
            monto_cuota = data.get("monto_cuota"),
            fecha_inicio = data["fecha_inicio"],
            es_especial = data.get("es_especial", False)
        )
        session.add(nuevo)
        session.commit()
        return jsonify({"msg":"Préstamo creado", "id": nuevo.id_prestamo}), 201
    except SQLAlchemyError as e:
        session.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()
