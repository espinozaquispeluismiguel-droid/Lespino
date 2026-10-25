"""Lógica de validación cruzada de paquetes (Fase 4).

registrar_paquete() ejecuta, en UNA transacción:
  1. Carga la calle (+ layout) y verifica que esté abierta.
  2. Verifica que el usuario esté asignado a la calle (directo o vía equipo).
  3. Bloquea el número de paquete (advisory lock en PostgreSQL) para evitar que dos
     operarios registren el mismo paquete a la vez.
  4. Detecta duplicados: un paquete solo puede tener UN conteo vigente por layout.
     Con reconteo=True se sustituye el anterior (queda trazado, vigente=false).
  5. Cruza contra `producto`:
       - existe en el layout  -> cantidad_esperada, coincide, estado COINCIDE/DIFERENCIA
       - no existe / es de otro layout -> estado NO_CATALOGADO (sobrante)
  6. Inserta en `producto_inventario`, cambia la calle a EN_PROCESO si procede y
     escribe en `historial_calle`.
  7. Calcula el avance del layout para devolverlo y difundirlo por WebSocket.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    Area,
    AsignacionCalle,
    Calle,
    EquipoUsuario,
    EstadoCalle,
    EstadoConteo,
    EstadoProducto,
    Producto,
    ProductoInventario,
    RolUsuario,
    TipoEventoHistorial,
    Usuario,
)
from app.schemas.inventario import AvanceLayout, RegistroPaqueteIn
from app.services.historial_service import registrar_evento

CALLES_CERRADAS = {EstadoCalle.VERIFICADA, EstadoCalle.CON_INCIDENCIAS}


# --------------------------------------------------------------------------- errores
class InventarioError(Exception):
    status_code = 400
    codigo = "inventario_error"

    def __init__(self, mensaje: str, detalle: dict | None = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.detalle = detalle or {}


class CalleNoEncontrada(InventarioError):
    status_code, codigo = 404, "calle_no_encontrada"


class SinAsignacion(InventarioError):
    status_code, codigo = 403, "calle_no_asignada"


class CalleCerrada(InventarioError):
    status_code, codigo = 409, "calle_cerrada"


class PaqueteDuplicado(InventarioError):
    status_code, codigo = 409, "paquete_ya_contado"


# --------------------------------------------------------------------------- resultado
@dataclass
class ResultadoRegistro:
    registro: ProductoInventario
    calle: Calle
    id_layout: int
    es_reconteo: bool
    avance: AvanceLayout
    mensaje: str
    calle_cambio_estado: bool


# --------------------------------------------------------------------------- helpers
async def _cargar_calle(db: AsyncSession, id_calle: int) -> tuple[Calle, int]:
    row = (
        await db.execute(
            select(Calle, Area.id_layout).join(Area, Area.id == Calle.id_area).where(Calle.id == id_calle)
        )
    ).first()
    if row is None:
        raise CalleNoEncontrada(f"La calle {id_calle} no existe")
    return row[0], row[1]


async def resolver_equipo(
    db: AsyncSession, calle: Calle, usuario: Usuario, id_equipo_solicitado: int | None
) -> int | None:
    """Valida la asignación y devuelve el equipo con el que se registra el conteo."""
    equipos_usuario = set(
        (await db.scalars(select(EquipoUsuario.id_equipo).where(EquipoUsuario.id_usuario == usuario.id))).all()
    )
    asignaciones = (
        await db.scalars(
            select(AsignacionCalle).where(
                AsignacionCalle.id_calle == calle.id,
                AsignacionCalle.activa.is_(True),
                or_(
                    AsignacionCalle.id_usuario == usuario.id,
                    AsignacionCalle.id_equipo.in_(equipos_usuario or {-1}),
                ),
            )
        )
    ).all()

    es_operario = usuario.rol is RolUsuario.OPERARIO
    if es_operario and not asignaciones:
        raise SinAsignacion(f"No tienes asignada la calle {calle.codigo}")

    if id_equipo_solicitado is not None:
        if es_operario and id_equipo_solicitado not in equipos_usuario:
            raise SinAsignacion("No perteneces al equipo indicado")
        return id_equipo_solicitado

    equipos_asignados = [a.id_equipo for a in asignaciones if a.id_equipo in equipos_usuario]
    return equipos_asignados[0] if equipos_asignados else None


async def _bloquear_paquete(db: AsyncSession, numero: str) -> None:
    """Serializa registros concurrentes del mismo paquete (se libera al commit/rollback)."""
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"paquete:{numero}"})


async def _conteo_vigente(db: AsyncSession, id_layout: int, numero: str):
    return (
        await db.execute(
            select(ProductoInventario, Calle.codigo, Usuario.nombre_completo)
            .join(Calle, Calle.id == ProductoInventario.id_calle)
            .join(Area, Area.id == Calle.id_area)
            .join(Usuario, Usuario.id == ProductoInventario.id_usuario)
            .where(
                Area.id_layout == id_layout,
                ProductoInventario.numero_de_paquete == numero,
                ProductoInventario.vigente.is_(True),
            )
            .with_for_update(of=ProductoInventario)
        )
    ).first()


def _fmt(d: Decimal) -> str:
    """12.000 -> '12', 12.500 -> '12.5' (sin notación científica)."""
    return format(Decimal(d).normalize(), "f")


def _coincide(contada: Decimal, esperada: Decimal) -> bool:
    return abs(Decimal(contada) - Decimal(esperada)) <= Decimal(str(settings.TOLERANCIA_CANTIDAD))


async def calcular_avance_layout(db: AsyncSession, id_layout: int) -> AvanceLayout:
    total = await db.scalar(
        select(func.count(Producto.id)).where(
            Producto.id_layout == id_layout, Producto.estado == EstadoProducto.ACTIVO
        )
    )
    pi = ProductoInventario
    fila = (
        await db.execute(
            select(
                func.coalesce(func.sum(case((pi.estado != EstadoConteo.NO_CATALOGADO, 1), else_=0)), 0),
                func.coalesce(func.sum(case((pi.estado == EstadoConteo.COINCIDE, 1), else_=0)), 0),
                func.coalesce(func.sum(case((pi.estado == EstadoConteo.DIFERENCIA, 1), else_=0)), 0),
                func.coalesce(func.sum(case((pi.estado == EstadoConteo.NO_CATALOGADO, 1), else_=0)), 0),
            )
            .join(Calle, Calle.id == pi.id_calle)
            .join(Area, Area.id == Calle.id_area)
            .where(Area.id_layout == id_layout, pi.vigente.is_(True))
        )
    ).one()
    contados, coinciden, diferencias, no_cat = (int(x) for x in fila)
    total = int(total or 0)
    return AvanceLayout(
        id_layout=id_layout,
        total_catalogados=total,
        contados=contados,
        coinciden=coinciden,
        diferencias=diferencias,
        no_catalogados=no_cat,
        porcentaje_avance=round(contados * 100 / total, 2) if total else 0.0,
    )


async def resumen_calle(db: AsyncSession, id_calle: int) -> dict:
    pi = ProductoInventario
    fila = (
        await db.execute(
            select(
                func.count(pi.id),
                func.coalesce(func.sum(case((pi.estado == EstadoConteo.DIFERENCIA, 1), else_=0)), 0),
                func.coalesce(func.sum(case((pi.estado == EstadoConteo.NO_CATALOGADO, 1), else_=0)), 0),
            ).where(pi.id_calle == id_calle, pi.vigente.is_(True))
        )
    ).one()
    return {"paquetes_contados": int(fila[0]), "diferencias": int(fila[1]), "no_catalogados": int(fila[2])}


# --------------------------------------------------------------------------- caso de uso principal
async def registrar_paquete(db: AsyncSession, data: RegistroPaqueteIn, usuario: Usuario) -> ResultadoRegistro:
    try:
        calle, id_layout = await _cargar_calle(db, data.id_calle)
        if calle.estado in CALLES_CERRADAS:
            raise CalleCerrada(
                f"La calle {calle.codigo} está cerrada ({calle.estado.value}). Un supervisor debe reabrirla."
            )
        id_equipo = await resolver_equipo(db, calle, usuario, data.id_equipo)
        numero = data.numero_de_paquete  # ya normalizado por el schema

        await _bloquear_paquete(db, numero)

        # ---- duplicados / reconteo
        anterior = await _conteo_vigente(db, id_layout, numero)
        if anterior is not None and not data.reconteo:
            prev, codigo_prev, usuario_prev = anterior
            raise PaqueteDuplicado(
                f"El paquete {numero} ya fue contado en la calle {codigo_prev}",
                {
                    "id_producto_inventario": prev.id,
                    "id_calle": prev.id_calle,
                    "codigo_calle": codigo_prev,
                    "usuario": usuario_prev,
                    "cantidad_contada": float(prev.cantidad_contada),
                    "fecha_registro": prev.fecha_registro.isoformat() if prev.fecha_registro else None,
                    "sugerencia": "Reenvíe con reconteo=true para sustituir el conteo anterior",
                },
            )
        prev_reg = anterior[0] if anterior else None
        if prev_reg is not None:
            prev_reg.vigente = False
            await db.flush()  # libera el índice único parcial antes de insertar

        # ---- cruce contra el maestro
        producto = await db.scalar(select(Producto).where(Producto.numero_de_paquete == numero))
        observaciones = [data.observaciones] if data.observaciones else []

        if producto is not None and producto.id_layout == id_layout:
            esperada = Decimal(producto.cantidad)
            coincide = _coincide(data.cantidad_contada, esperada)
            estado = EstadoConteo.COINCIDE if coincide else EstadoConteo.DIFERENCIA
            articulo, nombre, um = producto.articulo, producto.nombre, producto.unidad_de_medida
            id_producto = producto.id
            if producto.estado is EstadoProducto.INACTIVO:
                observaciones.append("Producto inactivo en el maestro")
            mensaje = (
                "Cantidad correcta."
                if coincide
                else "Diferencia detectada: recuente el paquete y, si se confirma, regístrelo como reconteo."
            )
        else:
            esperada, coincide, estado = None, False, EstadoConteo.NO_CATALOGADO
            articulo, nombre = data.articulo, data.nombre
            um = (data.unidad_de_medida or "").upper() or None
            id_producto = None
            if producto is not None:
                observaciones.append(f"Paquete catalogado en otro layout (id_layout={producto.id_layout})")
            mensaje = "Paquete no catalogado: registrado como Sobrante."

        ahora = datetime.now(timezone.utc)
        registro = ProductoInventario(
            id_calle=calle.id,
            id_usuario=usuario.id,
            id_equipo=id_equipo,
            id_producto=id_producto,
            articulo=articulo,
            nombre=nombre,
            numero_de_paquete=numero,
            cantidad_contada=data.cantidad_contada,
            cantidad_esperada=esperada,
            coincide=coincide,
            estado=estado,
            unidad_de_medida=um,
            metodo_ingreso=data.metodo_ingreso,
            vigente=True,
            id_reemplaza_a=prev_reg.id if prev_reg else None,
            observaciones=" | ".join(observaciones) or None,
            ocr_confianza=data.ocr_confianza,
            fecha_registro=ahora,
        )
        db.add(registro)

        # ---- estado de la calle
        cambio_estado = False
        if calle.estado in (EstadoCalle.PENDIENTE, EstadoCalle.ASIGNADA):
            calle.estado = EstadoCalle.EN_PROCESO
            calle.fecha_inicio_conteo = ahora
            cambio_estado = True
            registrar_evento(
                db,
                id_calle=calle.id,
                id_usuario=usuario.id,
                id_equipo=id_equipo,
                tipo=TipoEventoHistorial.INICIO_CONTEO,
                descripcion=f"{usuario.nombre_completo} inicia el conteo de la calle {calle.codigo}",
            )

        await db.flush()  # obtiene registro.id

        # ---- trazabilidad
        tipo = (
            TipoEventoHistorial.PAQUETE_RECONTADO
            if prev_reg
            else TipoEventoHistorial.PAQUETE_NO_CATALOGADO
            if estado is EstadoConteo.NO_CATALOGADO
            else TipoEventoHistorial.PAQUETE_REGISTRADO
        )
        registrar_evento(
            db,
            id_calle=calle.id,
            id_usuario=usuario.id,
            id_equipo=id_equipo,
            id_producto_inventario=registro.id,
            numero_de_paquete=numero,
            tipo=tipo,
            descripcion=f"Paquete {numero}: {estado.value} (contado {_fmt(data.cantidad_contada)}"
            + (f", esperado {_fmt(esperada)})" if esperada is not None else ")"),
            datos={
                "metodo_ingreso": data.metodo_ingreso.value,
                "cantidad_contada": str(data.cantidad_contada),
                "cantidad_esperada": str(esperada) if esperada is not None else None,
                "coincide": coincide,
                "estado": estado.value,
                "reemplaza_a": prev_reg.id if prev_reg else None,
                "cantidad_anterior": str(prev_reg.cantidad_contada) if prev_reg else None,
            },
        )

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    avance = await calcular_avance_layout(db, id_layout)
    return ResultadoRegistro(
        registro=registro,
        calle=calle,
        id_layout=id_layout,
        es_reconteo=prev_reg is not None,
        avance=avance,
        mensaje=mensaje,
        calle_cambio_estado=cambio_estado,
    )


async def finalizar_calle(db: AsyncSession, id_calle: int, usuario: Usuario) -> tuple[Calle, int, dict]:
    try:
        calle, id_layout = await _cargar_calle(db, id_calle)
        if calle.estado in CALLES_CERRADAS:
            raise CalleCerrada(f"La calle {calle.codigo} ya está cerrada")
        await resolver_equipo(db, calle, usuario, None)  # valida asignación del operario

        resumen = await resumen_calle(db, id_calle)
        incidencias = resumen["diferencias"] + resumen["no_catalogados"]
        calle.estado = EstadoCalle.CON_INCIDENCIAS if incidencias else EstadoCalle.VERIFICADA
        calle.fecha_verificacion = datetime.now(timezone.utc)
        calle.id_usuario_verificador = usuario.id
        registrar_evento(
            db,
            id_calle=calle.id,
            id_usuario=usuario.id,
            tipo=TipoEventoHistorial.CALLE_FINALIZADA,
            descripcion=f"Calle {calle.codigo} cerrada como {calle.estado.value}",
            datos=resumen,
        )
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return calle, id_layout, resumen
