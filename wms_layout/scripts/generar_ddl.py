"""Genera sql/schema.sql (dialecto PostgreSQL) a partir de los modelos ORM.

    python -m scripts.generar_ddl
"""
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models import Base
from app.models import enums

dialect = postgresql.dialect()
out = ["-- =============================================================",
       "-- WMS Layout & Inventario - DDL PostgreSQL (generado desde los modelos ORM)",
       "-- Regenerar con: python -m scripts.generar_ddl",
       "-- =============================================================", "",
       "BEGIN;", ""]

tipos = [
    ("rol_usuario", enums.RolUsuario), ("estado_calle", enums.EstadoCalle),
    ("estado_producto", enums.EstadoProducto), ("estado_conteo", enums.EstadoConteo),
    ("metodo_ingreso", enums.MetodoIngreso), ("tipo_evento_historial", enums.TipoEventoHistorial),
]
out.append("-- Tipos ENUM")
for nombre, cls in tipos:
    vals = ", ".join(f"'{m.value}'" for m in cls)
    out.append(f"CREATE TYPE {nombre} AS ENUM ({vals});")
out.append("")

for table in Base.metadata.sorted_tables:
    out.append(f"-- {table.name}")
    out.append(str(CreateTable(table).compile(dialect=dialect)).strip() + ";")
    for idx in sorted(table.indexes, key=lambda i: i.name):
        out.append(str(CreateIndex(idx).compile(dialect=dialect)).strip() + ";")
    out.append("")

out += [
    "-- Trigger: updated_at automático también para escrituras fuera del ORM",
    "CREATE OR REPLACE FUNCTION fn_set_updated_at() RETURNS trigger AS $$",
    "BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;",
]
for table in Base.metadata.sorted_tables:
    if "updated_at" in table.c:
        out.append(f"CREATE TRIGGER trg_{table.name}_updated_at BEFORE UPDATE ON {table.name} "
                   f"FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();")
out += ["", "COMMIT;", ""]

Path("sql").mkdir(exist_ok=True)
Path("sql/schema.sql").write_text("\n".join(out), encoding="utf-8")
print("sql/schema.sql generado")
