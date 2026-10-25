"""Carga masiva del maestro `producto` desde Excel.

Flujo:
  1. Leer el archivo (pandas + openpyxl) en un hilo aparte para no bloquear el event loop.
  2. Normalizar cabeceras y aceptar alias habituales ("Nº Paquete", "Descripción", "UM"...).
  3. Validar fila a fila (obligatorios, cantidad numérica >= 0, duplicados dentro del archivo).
  4. Upsert por lotes contra la BD (portable: PostgreSQL y SQLite para tests).
  5. Modo "reemplazar": inactivar los productos del layout que no vienen en el archivo.
  6. dry_run => se valida y simula todo, pero se hace ROLLBACK.
"""
from __future__ import annotations

import io
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models import EstadoProducto, Producto
from app.schemas.producto import ErrorFila, ModoImportacion, ResultadoImportacion
from app.services.normalizacion import normalizar_cabecera, normalizar_paquete

MAX_ERRORES_REPORTADOS = 500
# Límite seguro de parámetros por sentencia IN (asyncpg admite 32767)
LOTE_IN = 5000

COLUMNAS_OBLIGATORIAS = ("articulo", "nombre", "numero_de_paquete", "cantidad")

ALIAS_COLUMNAS: dict[str, str] = {
    # numero_de_paquete
    "numero_de_paquete": "numero_de_paquete", "numero_paquete": "numero_de_paquete",
    "n_paquete": "numero_de_paquete", "no_paquete": "numero_de_paquete", "nro_paquete": "numero_de_paquete",
    "num_paquete": "numero_de_paquete", "paquete": "numero_de_paquete", "package": "numero_de_paquete",
    "lote": "numero_de_paquete", "n_de_paquete": "numero_de_paquete",
    # articulo
    "articulo": "articulo", "cod_articulo": "articulo", "codigo_articulo": "articulo",
    "codigo": "articulo", "sku": "articulo", "referencia": "articulo", "item": "articulo",
    # nombre
    "nombre": "nombre", "descripcion": "nombre", "desc": "nombre", "nombre_articulo": "nombre",
    "description": "nombre",
    # cantidad
    "cantidad": "cantidad", "cant": "cantidad", "qty": "cantidad", "unidades": "cantidad",
    "cantidad_teorica": "cantidad", "stock": "cantidad",
    # unidad
    "unidad_de_medida": "unidad_de_medida", "unidad_medida": "unidad_de_medida",
    "unidad": "unidad_de_medida", "um": "unidad_de_medida", "u_m": "unidad_de_medida", "uom": "unidad_de_medida",
    # estado
    "estado": "estado",
}


class ExcelFormatoError(ValueError):
    """Error de estructura del archivo (no de una fila concreta)."""


@dataclass(slots=True)
class FilaProducto:
    fila: int
    articulo: str
    nombre: str
    numero_de_paquete: str
    cantidad: Decimal
    unidad_de_medida: str
    estado: EstadoProducto


# --------------------------------------------------------------------------- lectura
def _leer_excel(contenido: bytes) -> pd.DataFrame:
    try:
        # dtype=str: preserva ceros a la izquierda en códigos de paquete/artículo
        df = pd.read_excel(io.BytesIO(contenido), dtype=str, engine="openpyxl")
    except Exception as exc:  # archivo corrupto, no es xlsx, etc.
        raise ExcelFormatoError(f"No se pudo leer el Excel: {exc}") from exc

    df.columns = [ALIAS_COLUMNAS.get(normalizar_cabecera(c), normalizar_cabecera(c)) for c in df.columns]
    if df.columns.duplicated().any():
        dup = sorted(set(df.columns[df.columns.duplicated()]))
        raise ExcelFormatoError(f"Columnas duplicadas tras normalizar cabeceras: {dup}")

    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ExcelFormatoError(
            f"Faltan columnas obligatorias: {faltan}. Columnas detectadas: {list(df.columns)}"
        )
    # Elimina filas completamente vacías (muy frecuente al final de los Excel)
    return df.dropna(how="all")


def _texto(v: object) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return ""
    return str(v).strip()


def _validar_filas(df: pd.DataFrame) -> tuple[list[FilaProducto], list[ErrorFila]]:
    validas: list[FilaProducto] = []
    errores: list[ErrorFila] = []
    vistos: dict[str, int] = {}

    tiene_um = "unidad_de_medida" in df.columns
    tiene_estado = "estado" in df.columns

    for idx, row in zip(df.index, df.to_dict("records")):
        n_fila = int(idx) + 2  # +1 por cabecera, +1 porque Excel empieza en 1
        errs: list[str] = []

        paquete = normalizar_paquete(_texto(row.get("numero_de_paquete")))
        articulo = _texto(row.get("articulo"))
        nombre = _texto(row.get("nombre"))
        cant_raw = _texto(row.get("cantidad")).replace(",", ".")

        if not paquete:
            errs.append("numero_de_paquete vacío")
        elif len(paquete) > 80:
            errs.append("numero_de_paquete supera 80 caracteres")
        if not articulo:
            errs.append("articulo vacío")
        if not nombre:
            errs.append("nombre vacío")

        cantidad: Decimal | None = None
        try:
            cantidad = Decimal(cant_raw)
            if not cantidad.is_finite():
                raise InvalidOperation
            if cantidad < 0:
                errs.append("cantidad negativa")
            cantidad = cantidad.quantize(Decimal("0.001"))
        except (InvalidOperation, ValueError):
            errs.append(f"cantidad no numérica: '{cant_raw}'")

        um = (_texto(row.get("unidad_de_medida")) if tiene_um else "").upper() or "UND"

        estado = EstadoProducto.ACTIVO
        if tiene_estado and _texto(row.get("estado")):
            try:
                estado = EstadoProducto(_texto(row.get("estado")).lower())
            except ValueError:
                errs.append(f"estado inválido '{row.get('estado')}' (use activo/inactivo)")

        if paquete and paquete in vistos:
            errs.append(f"numero_de_paquete duplicado en el archivo (ya aparece en fila {vistos[paquete]})")

        if errs:
            errores.append(ErrorFila(fila=n_fila, numero_de_paquete=paquete or None, errores=errs))
            continue

        vistos[paquete] = n_fila
        validas.append(
            FilaProducto(
                fila=n_fila,
                articulo=articulo[:60],
                nombre=nombre[:255],
                numero_de_paquete=paquete,
                cantidad=cantidad,  # type: ignore[arg-type]
                unidad_de_medida=um[:20],
                estado=estado,
            )
        )
    return validas, errores


# --------------------------------------------------------------------------- persistencia
def _hay_cambios(p: Producto, f: FilaProducto) -> bool:
    return (
        p.articulo != f.articulo
        or p.nombre != f.nombre
        or Decimal(p.cantidad) != f.cantidad
        or p.unidad_de_medida != f.unidad_de_medida
        or p.estado != f.estado
    )


async def importar_productos_excel(
    db: AsyncSession,
    *,
    contenido: bytes,
    nombre_archivo: str,
    id_layout: int,
    modo: ModoImportacion = ModoImportacion.UPSERT,
    dry_run: bool = False,
    permitir_parcial: bool = True,
) -> ResultadoImportacion:
    t0 = time.perf_counter()

    df = await run_in_threadpool(_leer_excel, contenido)
    validas, errores = await run_in_threadpool(_validar_filas, df)

    res = ResultadoImportacion(
        id_layout=id_layout,
        archivo=nombre_archivo,
        modo=modo,
        dry_run=dry_run,
        aplicado=False,
        total_filas=len(df),
        filas_validas=len(validas),
    )

    chunk = settings.EXCEL_CHUNK_SIZE
    for i in range(0, len(validas), chunk):
        lote = validas[i : i + chunk]
        por_paquete = {f.numero_de_paquete: f for f in lote}
        existentes = (
            await db.scalars(select(Producto).where(Producto.numero_de_paquete.in_(por_paquete.keys())))
        ).all()
        mapa = {p.numero_de_paquete: p for p in existentes}

        nuevos: list[Producto] = []
        for f in lote:
            p = mapa.get(f.numero_de_paquete)
            if p is None:
                nuevos.append(
                    Producto(
                        id_layout=id_layout,
                        articulo=f.articulo,
                        nombre=f.nombre,
                        numero_de_paquete=f.numero_de_paquete,
                        cantidad=f.cantidad,
                        unidad_de_medida=f.unidad_de_medida,
                        estado=f.estado,
                    )
                )
            elif p.id_layout != id_layout:
                # numero_de_paquete es UNIQUE global: no se "roba" un paquete de otro layout
                errores.append(
                    ErrorFila(
                        fila=f.fila,
                        numero_de_paquete=f.numero_de_paquete,
                        errores=[f"el paquete ya existe en otro layout (id_layout={p.id_layout})"],
                    )
                )
                res.filas_validas -= 1
            elif _hay_cambios(p, f):
                p.articulo, p.nombre, p.cantidad = f.articulo, f.nombre, f.cantidad
                p.unidad_de_medida, p.estado = f.unidad_de_medida, f.estado
                res.actualizados += 1
            else:
                res.sin_cambios += 1

        db.add_all(nuevos)
        res.insertados += len(nuevos)
        await db.flush()

    if modo is ModoImportacion.REEMPLAZAR:
        en_archivo = {f.numero_de_paquete for f in validas}
        activos = (
            await db.execute(
                select(Producto.id, Producto.numero_de_paquete).where(
                    Producto.id_layout == id_layout, Producto.estado == EstadoProducto.ACTIVO
                )
            )
        ).all()
        a_inactivar = [pid for pid, num in activos if num not in en_archivo]
        for i in range(0, len(a_inactivar), LOTE_IN):
            await db.execute(
                update(Producto)
                .where(Producto.id.in_(a_inactivar[i : i + LOTE_IN]))
                .values(estado=EstadoProducto.INACTIVO)
                .execution_options(synchronize_session=False)
            )
        res.inactivados = len(a_inactivar)

    errores.sort(key=lambda e: e.fila)
    res.filas_con_error = len(errores)
    res.errores = errores[:MAX_ERRORES_REPORTADOS]
    res.errores_truncados = len(errores) > MAX_ERRORES_REPORTADOS

    if dry_run or (errores and not permitir_parcial):
        await db.rollback()
    else:
        await db.commit()
        res.aplicado = True

    res.duracion_ms = int((time.perf_counter() - t0) * 1000)
    return res


def generar_plantilla() -> bytes:
    """Excel de ejemplo con las columnas esperadas."""
    df = pd.DataFrame(
        [
            {"articulo": "ART-001", "nombre": "Tablero melamina 18mm", "numero_de_paquete": "PKG000123",
             "cantidad": 25, "unidad_de_medida": "UND", "estado": "activo"},
            {"articulo": "ART-002", "nombre": "Perfil aluminio 6m", "numero_de_paquete": "PKG000124",
             "cantidad": 12.5, "unidad_de_medida": "M", "estado": "activo"},
        ]
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False, sheet_name="productos")
    return buf.getvalue()
