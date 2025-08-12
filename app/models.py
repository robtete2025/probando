from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Numeric, Date, ForeignKey
from datetime import datetime
from sqlalchemy.orm import relationship

Base = declarative_base()

class Usuario(Base):
    __tablename__ = "usuarios"
    id_usuario = Column(Integer, primary_key=True)
    nombre_usuario = Column(String(50), unique=True, nullable=False)
    clave_hash = Column(Text, nullable=False)
    nombre_completo = Column(String(255))
    rol = Column(String(20), nullable=False)  # 'admin' o 'trabajador'
    activo = Column(Boolean, default=True)
    creado_en = Column(DateTime, default=datetime.utcnow)

class Representante(Base):
    __tablename__ = "representantes"
    id_representante = Column(Integer, primary_key=True)
    nombre = Column(String(255), nullable=False)
    telefono = Column(String(15))
    id_usuario = Column(Integer, ForeignKey("usuarios.id_usuario"))

class Mercado(Base):
    __tablename__ = "mercados"
    id_mercado = Column(Integer, primary_key=True)
    nombre = Column(String(255), nullable=False)
    id_representante = Column(Integer, ForeignKey("representantes.id_representante"))

class Cliente(Base):
    __tablename__ = "clientes"
    id_cliente = Column(Integer, primary_key=True)
    dni = Column(String(15), unique=True, nullable=False)
    nombre_completo = Column(String(255), nullable=False)
    telefono = Column(String(15))

class Prestamo(Base):
    __tablename__ = "prestamos"
    id_prestamo = Column(Integer, primary_key=True)
    id_cliente = Column(Integer, ForeignKey("clientes.id_cliente"), nullable=False)
    monto_total = Column(Numeric(10,2), nullable=False)
    saldo = Column(Numeric(10,2), nullable=False)
    tipo = Column(String(20))
    dias_transcurridos = Column(Integer)
    cuotas_pagadas = Column(Integer)
    deuda_vencida = Column(Numeric(10,2))
    monto_cuota = Column(Numeric(10,2))
    fecha_inicio = Column(Date, nullable=False)
    es_especial = Column(Boolean, default=False)

class ResumenCobranza(Base):
    __tablename__ = "resumen_cobranza"
    id_resumen = Column(Integer, primary_key=True)
    id_mercado = Column(Integer, ForeignKey("mercados.id_mercado"), nullable=False)
    fecha = Column(Date, nullable=False)
    total_creditos = Column(Integer)
    clientes_vigentes = Column(Integer)
    creditos_vencidos = Column(Integer)
    total_deuda = Column(Numeric(12,2))
    total_cobranza = Column(Numeric(12,2))
    saldo_vencido = Column(Numeric(12,2))
    saldo_alto_riesgo = Column(Numeric(12,2))
    saldo_bajo_riesgo = Column(Numeric(12,2))
    saldo_refinanciado = Column(Numeric(12,2))
