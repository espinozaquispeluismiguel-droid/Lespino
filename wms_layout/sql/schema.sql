-- =============================================================
-- WMS Layout & Inventario - DDL PostgreSQL (generado desde los modelos ORM)
-- Regenerar con: python -m scripts.generar_ddl
-- =============================================================

BEGIN;

-- Tipos ENUM
CREATE TYPE rol_usuario AS ENUM ('administrador', 'supervisor', 'operario');
CREATE TYPE estado_calle AS ENUM ('pendiente', 'asignada', 'en_proceso', 'verificada', 'con_incidencias');
CREATE TYPE estado_producto AS ENUM ('activo', 'inactivo');
CREATE TYPE estado_conteo AS ENUM ('coincide', 'diferencia', 'no_catalogado');
CREATE TYPE metodo_ingreso AS ENUM ('manual', 'qr', 'foto_ia');
CREATE TYPE tipo_evento_historial AS ENUM ('calle_creada', 'calle_asignada', 'inicio_conteo', 'paquete_registrado', 'paquete_recontado', 'paquete_no_catalogado', 'calle_finalizada', 'calle_reabierta');

-- organizacion
CREATE TABLE organizacion (
	id SERIAL NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	identificador_fiscal VARCHAR(30), 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_organizacion PRIMARY KEY (id), 
	CONSTRAINT uq_organizacion_identificador_fiscal UNIQUE (identificador_fiscal)
);

-- delegacion
CREATE TABLE delegacion (
	id SERIAL NOT NULL, 
	id_organizacion INTEGER NOT NULL, 
	nombre VARCHAR(150) NOT NULL, 
	direccion VARCHAR(255), 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_delegacion PRIMARY KEY (id), 
	CONSTRAINT fk_delegacion_id_organizacion_organizacion FOREIGN KEY(id_organizacion) REFERENCES organizacion (id) ON DELETE RESTRICT
);
CREATE INDEX ix_delegacion_id_organizacion ON delegacion (id_organizacion);

-- equipo
CREATE TABLE equipo (
	id SERIAL NOT NULL, 
	id_delegacion INTEGER NOT NULL, 
	nombre VARCHAR(100) NOT NULL, 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_equipo PRIMARY KEY (id), 
	CONSTRAINT fk_equipo_id_delegacion_delegacion FOREIGN KEY(id_delegacion) REFERENCES delegacion (id) ON DELETE RESTRICT
);
CREATE INDEX ix_equipo_id_delegacion ON equipo (id_delegacion);

-- usuario
CREATE TABLE usuario (
	id SERIAL NOT NULL, 
	id_delegacion INTEGER NOT NULL, 
	username VARCHAR(60) NOT NULL, 
	email VARCHAR(150), 
	nombre_completo VARCHAR(150) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	rol rol_usuario NOT NULL, 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	intentos_fallidos SMALLINT DEFAULT '0' NOT NULL, 
	bloqueado BOOLEAN DEFAULT 'false' NOT NULL, 
	bloqueado_hasta TIMESTAMP WITH TIME ZONE, 
	ultimo_acceso TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_usuario PRIMARY KEY (id), 
	CONSTRAINT fk_usuario_id_delegacion_delegacion FOREIGN KEY(id_delegacion) REFERENCES delegacion (id) ON DELETE RESTRICT, 
	CONSTRAINT uq_usuario_username UNIQUE (username), 
	CONSTRAINT uq_usuario_email UNIQUE (email)
);
CREATE INDEX ix_usuario_id_delegacion ON usuario (id_delegacion);

-- equipo_usuario
CREATE TABLE equipo_usuario (
	id_equipo INTEGER NOT NULL, 
	id_usuario INTEGER NOT NULL, 
	es_lider BOOLEAN DEFAULT 'false' NOT NULL, 
	fecha_alta TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_equipo_usuario PRIMARY KEY (id_equipo, id_usuario), 
	CONSTRAINT fk_equipo_usuario_id_equipo_equipo FOREIGN KEY(id_equipo) REFERENCES equipo (id) ON DELETE CASCADE, 
	CONSTRAINT fk_equipo_usuario_id_usuario_usuario FOREIGN KEY(id_usuario) REFERENCES usuario (id) ON DELETE CASCADE
);
CREATE INDEX ix_equipo_usuario_id_usuario ON equipo_usuario (id_usuario);

-- layout
CREATE TABLE layout (
	id SERIAL NOT NULL, 
	id_delegacion INTEGER NOT NULL, 
	nombre VARCHAR(120) NOT NULL, 
	descripcion TEXT, 
	ancho NUMERIC(10, 2), 
	alto NUMERIC(10, 2), 
	activo BOOLEAN DEFAULT 'true' NOT NULL, 
	id_usuario_creador INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_layout PRIMARY KEY (id), 
	CONSTRAINT uq_layout_id_delegacion_nombre UNIQUE (id_delegacion, nombre), 
	CONSTRAINT fk_layout_id_delegacion_delegacion FOREIGN KEY(id_delegacion) REFERENCES delegacion (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_layout_id_usuario_creador_usuario FOREIGN KEY(id_usuario_creador) REFERENCES usuario (id) ON DELETE SET NULL
);
CREATE INDEX ix_layout_id_delegacion ON layout (id_delegacion);

-- area
CREATE TABLE area (
	id SERIAL NOT NULL, 
	id_layout INTEGER NOT NULL, 
	nombre VARCHAR(80) NOT NULL, 
	color VARCHAR(9), 
	coord_x NUMERIC(10, 2), 
	coord_y NUMERIC(10, 2), 
	ancho NUMERIC(10, 2), 
	alto NUMERIC(10, 2), 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_area PRIMARY KEY (id), 
	CONSTRAINT uq_area_id_layout_nombre UNIQUE (id_layout, nombre), 
	CONSTRAINT fk_area_id_layout_layout FOREIGN KEY(id_layout) REFERENCES layout (id) ON DELETE CASCADE
);
CREATE INDEX ix_area_id_layout ON area (id_layout);

-- producto
CREATE TABLE producto (
	id BIGSERIAL NOT NULL, 
	id_layout INTEGER NOT NULL, 
	articulo VARCHAR(60) NOT NULL, 
	nombre VARCHAR(255) NOT NULL, 
	numero_de_paquete VARCHAR(80) NOT NULL, 
	cantidad NUMERIC(14, 3) NOT NULL, 
	estado estado_producto DEFAULT 'activo' NOT NULL, 
	unidad_de_medida VARCHAR(20) DEFAULT 'UND' NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_producto PRIMARY KEY (id), 
	CONSTRAINT ck_producto_cantidad_no_negativa CHECK (cantidad >= 0), 
	CONSTRAINT fk_producto_id_layout_layout FOREIGN KEY(id_layout) REFERENCES layout (id) ON DELETE CASCADE, 
	CONSTRAINT uq_producto_numero_de_paquete UNIQUE (numero_de_paquete)
);
CREATE INDEX ix_producto_layout_articulo ON producto (id_layout, articulo);

-- calle
CREATE TABLE calle (
	id SERIAL NOT NULL, 
	id_area INTEGER NOT NULL, 
	codigo VARCHAR(20) NOT NULL, 
	coord_x NUMERIC(10, 2), 
	coord_y NUMERIC(10, 2), 
	ancho NUMERIC(10, 2), 
	alto NUMERIC(10, 2), 
	rotacion NUMERIC(5, 2), 
	estado estado_calle DEFAULT 'pendiente' NOT NULL, 
	fecha_inicio_conteo TIMESTAMP WITH TIME ZONE, 
	fecha_verificacion TIMESTAMP WITH TIME ZONE, 
	id_usuario_verificador INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_calle PRIMARY KEY (id), 
	CONSTRAINT uq_calle_id_area_codigo UNIQUE (id_area, codigo), 
	CONSTRAINT fk_calle_id_area_area FOREIGN KEY(id_area) REFERENCES area (id) ON DELETE CASCADE, 
	CONSTRAINT fk_calle_id_usuario_verificador_usuario FOREIGN KEY(id_usuario_verificador) REFERENCES usuario (id) ON DELETE SET NULL
);
CREATE INDEX ix_calle_estado ON calle (estado);
CREATE INDEX ix_calle_id_area ON calle (id_area);

-- asignacion_calle
CREATE TABLE asignacion_calle (
	id SERIAL NOT NULL, 
	id_calle INTEGER NOT NULL, 
	id_usuario INTEGER, 
	id_equipo INTEGER, 
	id_usuario_asignador INTEGER, 
	fecha_asignacion TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	activa BOOLEAN DEFAULT 'true' NOT NULL, 
	CONSTRAINT pk_asignacion_calle PRIMARY KEY (id), 
	CONSTRAINT ck_asignacion_calle_destinatario CHECK (id_usuario IS NOT NULL OR id_equipo IS NOT NULL), 
	CONSTRAINT fk_asignacion_calle_id_calle_calle FOREIGN KEY(id_calle) REFERENCES calle (id) ON DELETE CASCADE, 
	CONSTRAINT fk_asignacion_calle_id_usuario_usuario FOREIGN KEY(id_usuario) REFERENCES usuario (id) ON DELETE CASCADE, 
	CONSTRAINT fk_asignacion_calle_id_equipo_equipo FOREIGN KEY(id_equipo) REFERENCES equipo (id) ON DELETE CASCADE, 
	CONSTRAINT fk_asignacion_calle_id_usuario_asignador_usuario FOREIGN KEY(id_usuario_asignador) REFERENCES usuario (id) ON DELETE SET NULL
);
CREATE INDEX ix_asignacion_calle_activa ON asignacion_calle (id_calle, activa);
CREATE INDEX ix_asignacion_calle_id_equipo ON asignacion_calle (id_equipo);
CREATE INDEX ix_asignacion_calle_id_usuario ON asignacion_calle (id_usuario);

-- producto_inventario
CREATE TABLE producto_inventario (
	id BIGSERIAL NOT NULL, 
	id_calle INTEGER NOT NULL, 
	id_usuario INTEGER NOT NULL, 
	id_equipo INTEGER, 
	id_producto BIGINT, 
	articulo VARCHAR(60), 
	nombre VARCHAR(255), 
	numero_de_paquete VARCHAR(80) NOT NULL, 
	cantidad_contada NUMERIC(14, 3) NOT NULL, 
	cantidad_esperada NUMERIC(14, 3), 
	coincide BOOLEAN DEFAULT 'false' NOT NULL, 
	estado estado_conteo NOT NULL, 
	unidad_de_medida VARCHAR(20), 
	metodo_ingreso metodo_ingreso NOT NULL, 
	vigente BOOLEAN DEFAULT 'true' NOT NULL, 
	id_reemplaza_a BIGINT, 
	observaciones TEXT, 
	ocr_confianza NUMERIC(5, 2), 
	fecha_registro TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_producto_inventario PRIMARY KEY (id), 
	CONSTRAINT ck_producto_inventario_contada_no_negativa CHECK (cantidad_contada >= 0), 
	CONSTRAINT fk_producto_inventario_id_calle_calle FOREIGN KEY(id_calle) REFERENCES calle (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_producto_inventario_id_usuario_usuario FOREIGN KEY(id_usuario) REFERENCES usuario (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_producto_inventario_id_equipo_equipo FOREIGN KEY(id_equipo) REFERENCES equipo (id) ON DELETE SET NULL, 
	CONSTRAINT fk_producto_inventario_id_producto_producto FOREIGN KEY(id_producto) REFERENCES producto (id) ON DELETE SET NULL, 
	CONSTRAINT fk_producto_inventario_id_reemplaza_a_producto_inventario FOREIGN KEY(id_reemplaza_a) REFERENCES producto_inventario (id) ON DELETE SET NULL
);
CREATE INDEX ix_prodinv_calle_fecha ON producto_inventario (id_calle, fecha_registro);
CREATE INDEX ix_prodinv_paquete_vigente ON producto_inventario (numero_de_paquete, vigente);
CREATE INDEX ix_prodinv_usuario_fecha ON producto_inventario (id_usuario, fecha_registro);
CREATE INDEX ix_producto_inventario_id_producto ON producto_inventario (id_producto);
CREATE UNIQUE INDEX uq_prodinv_calle_paquete_vigente ON producto_inventario (id_calle, numero_de_paquete) WHERE vigente;

-- historial_calle
CREATE TABLE historial_calle (
	id BIGSERIAL NOT NULL, 
	id_calle INTEGER NOT NULL, 
	id_usuario INTEGER, 
	id_equipo INTEGER, 
	id_producto_inventario BIGINT, 
	tipo_evento tipo_evento_historial NOT NULL, 
	descripcion TEXT NOT NULL, 
	datos JSONB, 
	numero_de_paquete TEXT, 
	fecha TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
	CONSTRAINT pk_historial_calle PRIMARY KEY (id), 
	CONSTRAINT fk_historial_calle_id_calle_calle FOREIGN KEY(id_calle) REFERENCES calle (id) ON DELETE CASCADE, 
	CONSTRAINT fk_historial_calle_id_usuario_usuario FOREIGN KEY(id_usuario) REFERENCES usuario (id) ON DELETE SET NULL, 
	CONSTRAINT fk_historial_calle_id_equipo_equipo FOREIGN KEY(id_equipo) REFERENCES equipo (id) ON DELETE SET NULL, 
	CONSTRAINT fk_historial_calle_id_producto_inventario_producto_inventario FOREIGN KEY(id_producto_inventario) REFERENCES producto_inventario (id) ON DELETE SET NULL
);
CREATE INDEX ix_historial_calle_fecha ON historial_calle (id_calle, fecha);
CREATE INDEX ix_historial_calle_numero_de_paquete ON historial_calle (numero_de_paquete);
CREATE INDEX ix_historial_usuario_fecha ON historial_calle (id_usuario, fecha);

-- Trigger: updated_at automático también para escrituras fuera del ORM
CREATE OR REPLACE FUNCTION fn_set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_organizacion_updated_at BEFORE UPDATE ON organizacion FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_delegacion_updated_at BEFORE UPDATE ON delegacion FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_equipo_updated_at BEFORE UPDATE ON equipo FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_usuario_updated_at BEFORE UPDATE ON usuario FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_layout_updated_at BEFORE UPDATE ON layout FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_area_updated_at BEFORE UPDATE ON area FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_producto_updated_at BEFORE UPDATE ON producto FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_calle_updated_at BEFORE UPDATE ON calle FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

COMMIT;
