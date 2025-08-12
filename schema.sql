-- TABLAS
CREATE TABLE usuarios (
    id_usuario SERIAL PRIMARY KEY,
    nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
    clave_hash TEXT NOT NULL,
    nombre_completo VARCHAR(255),
    rol VARCHAR(20) NOT NULL CHECK (rol IN ('admin', 'trabajador')),
    activo BOOLEAN DEFAULT TRUE,
    creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE representantes (
    id_representante SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    telefono VARCHAR(15),
    id_usuario INT REFERENCES usuarios(id_usuario) ON DELETE SET NULL
);

CREATE TABLE mercados (
    id_mercado SERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    id_representante INT REFERENCES representantes(id_representante) ON DELETE SET NULL
);

CREATE TABLE clientes (
    id_cliente SERIAL PRIMARY KEY,
    dni VARCHAR(15) UNIQUE NOT NULL,
    nombre_completo VARCHAR(255) NOT NULL,
    telefono VARCHAR(15)
);

CREATE TABLE prestamos (
    id_prestamo SERIAL PRIMARY KEY,
    id_cliente INT REFERENCES clientes(id_cliente) ON DELETE CASCADE,
    monto_total NUMERIC(10,2) NOT NULL,
    saldo NUMERIC(10,2) NOT NULL,
    tipo VARCHAR(20),
    dias_transcurridos INT,
    cuotas_pagadas INT,
    deuda_vencida NUMERIC(10,2),
    monto_cuota NUMERIC(10,2),
    fecha_inicio DATE NOT NULL,
    es_especial BOOLEAN DEFAULT FALSE
);

CREATE TABLE resumen_cobranza (
    id_resumen SERIAL PRIMARY KEY,
    id_mercado INT REFERENCES mercados(id_mercado) ON DELETE CASCADE,
    fecha DATE NOT NULL,
    total_creditos INT,
    clientes_vigentes INT,
    creditos_vencidos INT,
    total_deuda NUMERIC(12,2),
    total_cobranza NUMERIC(12,2),
    saldo_vencido NUMERIC(12,2),
    saldo_alto_riesgo NUMERIC(12,2),
    saldo_bajo_riesgo NUMERIC(12,2),
    saldo_refinanciado NUMERIC(12,2)
);

-- SECUENCIAS y permisos básicos (las secuencias las maneja postgres automáticamente al crear SERIAL)
