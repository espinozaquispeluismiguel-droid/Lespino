"""Fase 4: ejecución de inventario por paquete (vista operario)."""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cualquier_rol, supervisor_o_admin
from app.core.config import settings
from app.core.database import get_db
from app.models import (
    Area, AsignacionCalle, Calle, Equipo, EquipoUsuario, EstadoCalle, EstadoConteo, Layout, MetodoIngreso,
    Producto, ProductoInventario, RolUsuario, TipoEventoHistorial, Usuario,
)
from app.schemas.almacen import MiCalleOut
from app.services.almacen_service import obtener_calle, stats_por_calle
from app.services.historial_service import registrar_evento
from app.schemas.inventario import DatosOCR, FinalizarCalleOut, RegistroPaqueteIn, ResultadoValidacion
from app.services import inventario_service as svc
from app.services.ocr_service import OCRNoDisponible, analizar_etiqueta
from app.websockets.manager import canal_layout, manager

router = APIRouter(prefix="/inventario", tags=["Inventario (operario)"])

MAX_FOTO_MB = 8


def _error(exc: svc.InventarioError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"codigo": exc.codigo, "detail": exc.mensaje, "contexto": exc.detalle},
    )


@router.post(
    "/registrar",
    response_model=ResultadoValidacion,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar y validar un paquete contado",
    responses={403: {"description": "Calle no asignada"}, 409: {"description": "Paquete ya contado / calle cerrada"}},
)
async def registrar_paquete(
    data: RegistroPaqueteIn,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(cualquier_rol),
):
    try:
        r = await svc.registrar_paquete(db, data, usuario)
    except svc.InventarioError as exc:
        return _error(exc)

    reg = r.registro
    diferencia = (
        reg.cantidad_contada - reg.cantidad_esperada if reg.cantidad_esperada is not None else None
    )
    ocultar = settings.CONTEO_CIEGO and usuario.rol is RolUsuario.OPERARIO

    resultado = ResultadoValidacion(
        id=reg.id,
        id_calle=reg.id_calle,
        codigo_calle=r.calle.codigo,
        numero_de_paquete=reg.numero_de_paquete,
        estado=reg.estado,
        coincide=reg.coincide,
        cantidad_contada=reg.cantidad_contada,
        cantidad_esperada=None if ocultar else reg.cantidad_esperada,
        diferencia=None if ocultar else diferencia,
        articulo=reg.articulo,
        nombre=reg.nombre,
        unidad_de_medida=reg.unidad_de_medida,
        metodo_ingreso=reg.metodo_ingreso,
        es_reconteo=r.es_reconteo,
        estado_calle=r.calle.estado,
        mensaje=r.mensaje,
        fecha_registro=reg.fecha_registro,
        avance=r.avance,
    )

    # Tiempo real: el dashboard del supervisor SÍ recibe la cantidad esperada
    resumen = await svc.resumen_calle(db, r.calle.id)
    await manager.broadcast(
        canal_layout(r.id_layout),
        "paquete_registrado",
        {
            **resultado.model_dump(exclude={"avance"}),
            "cantidad_esperada": reg.cantidad_esperada,
            "diferencia": diferencia,
            "usuario": usuario.nombre_completo,
            "avance": r.avance.model_dump(),
            "calle": {"id": r.calle.id, "codigo": r.calle.codigo, "estado": r.calle.estado, **resumen},
        },
    )
    return resultado


@router.post("/ocr", response_model=DatosOCR, summary="Extraer datos de la foto de una etiqueta (no registra)")
async def ocr_etiqueta(
    foto: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _u: Usuario = Depends(cualquier_rol),
):
    if foto.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Use JPG, PNG o WEBP")
    contenido = await foto.read(MAX_FOTO_MB * 1024 * 1024 + 1)
    if len(contenido) > MAX_FOTO_MB * 1024 * 1024:
        raise HTTPException(413, f"La foto supera {MAX_FOTO_MB} MB")
    try:
        from starlette.concurrency import run_in_threadpool

        datos = await run_in_threadpool(analizar_etiqueta, contenido)
    except OCRNoDisponible as exc:
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    if datos.numero_de_paquete:
        p = await db.scalar(select(Producto).where(Producto.numero_de_paquete == datos.numero_de_paquete))
        if p:
            datos.producto_encontrado = True
            datos.nombre_catalogo = p.nombre
            datos.articulo = datos.articulo or p.articulo
            datos.unidad_de_medida = datos.unidad_de_medida or p.unidad_de_medida
    return datos


@router.post("/calles/{id_calle}/finalizar", response_model=FinalizarCalleOut, summary="Cerrar el conteo de una calle")
async def finalizar_calle(
    id_calle: int,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(cualquier_rol),
):
    try:
        calle, id_layout, resumen = await svc.finalizar_calle(db, id_calle, usuario)
    except svc.InventarioError as exc:
        return _error(exc)

    await manager.broadcast(
        canal_layout(id_layout),
        "calle_finalizada",
        {"id": calle.id, "codigo": calle.codigo, "estado": calle.estado, **resumen},
    )
    return FinalizarCalleOut(id_calle=calle.id, estado=calle.estado, **resumen)


# --------------------------------------------------------------------------- consultas de apoyo a la UI
class RegistroOut(BaseModel):
    id: int
    numero_de_paquete: str
    articulo: str | None
    nombre: str | None
    cantidad_contada: Decimal
    cantidad_esperada: Decimal | None
    coincide: bool
    estado: EstadoConteo
    unidad_de_medida: str | None
    metodo_ingreso: MetodoIngreso
    usuario: str
    fecha_registro: datetime
    es_reconteo: bool


@router.get("/mis-calles", response_model=list[MiCalleOut], summary="Calles asignadas al usuario actual")
async def mis_calles(db: AsyncSession = Depends(get_db), u: Usuario = Depends(cualquier_rol)):
    equipos = select(EquipoUsuario.id_equipo).where(EquipoUsuario.id_usuario == u.id)
    rows = (
        await db.execute(
            select(Calle, Area.nombre, Layout.id, Layout.nombre, Equipo.nombre)
            .join(AsignacionCalle, AsignacionCalle.id_calle == Calle.id)
            .join(Area, Area.id == Calle.id_area)
            .join(Layout, Layout.id == Area.id_layout)
            .outerjoin(Equipo, Equipo.id == AsignacionCalle.id_equipo)
            .where(
                AsignacionCalle.activa.is_(True),
                or_(AsignacionCalle.id_usuario == u.id, AsignacionCalle.id_equipo.in_(equipos)),
            )
            .order_by(Layout.nombre, Area.nombre, Calle.codigo)
        )
    ).all()
    vistos, out = set(), []
    stats = await stats_por_calle(db, [r[0].id for r in rows])
    for calle, area, id_layout, layout, equipo in rows:
        if calle.id in vistos:
            continue
        vistos.add(calle.id)
        out.append(MiCalleOut(id_calle=calle.id, codigo=calle.codigo, area=area, id_layout=id_layout, layout=layout,
                              estado=calle.estado, equipo=equipo,
                              paquetes_contados=stats.get(calle.id, {}).get("paquetes_contados", 0)))
    return out


@router.get("/calles/{id_calle}/registros", response_model=list[RegistroOut])
async def registros_calle(id_calle: int, limit: int = Query(200, le=1000), db: AsyncSession = Depends(get_db),
                          u: Usuario = Depends(cualquier_rol)):
    calle, _ = await obtener_calle(db, id_calle, u)
    try:
        await svc.resolver_equipo(db, calle, u, None)
    except svc.InventarioError as exc:
        return _error(exc)
    pi = ProductoInventario
    rows = (
        await db.execute(
            select(pi, Usuario.nombre_completo)
            .join(Usuario, Usuario.id == pi.id_usuario)
            .where(pi.id_calle == id_calle, pi.vigente.is_(True))
            .order_by(pi.fecha_registro.desc(), pi.id.desc())
            .limit(limit)
        )
    ).all()
    ocultar = settings.CONTEO_CIEGO and u.rol is RolUsuario.OPERARIO
    return [
        RegistroOut(id=r.id, numero_de_paquete=r.numero_de_paquete, articulo=r.articulo, nombre=r.nombre,
                    cantidad_contada=r.cantidad_contada, cantidad_esperada=None if ocultar else r.cantidad_esperada,
                    coincide=r.coincide, estado=r.estado, unidad_de_medida=r.unidad_de_medida,
                    metodo_ingreso=r.metodo_ingreso, usuario=nombre, fecha_registro=r.fecha_registro,
                    es_reconteo=r.id_reemplaza_a is not None)
        for r, nombre in rows
    ]


@router.post("/calles/{id_calle}/reabrir", summary="Reabrir una calle cerrada (supervisor)")
async def reabrir_calle(id_calle: int, db: AsyncSession = Depends(get_db), u: Usuario = Depends(supervisor_o_admin)):
    calle, layout = await obtener_calle(db, id_calle, u)
    if calle.estado not in svc.CALLES_CERRADAS:
        raise HTTPException(409, f"La calle {calle.codigo} no está cerrada")
    calle.estado = EstadoCalle.EN_PROCESO
    calle.fecha_verificacion = None
    registrar_evento(db, id_calle=calle.id, id_usuario=u.id, tipo=TipoEventoHistorial.CALLE_REABIERTA,
                     descripcion=f"{u.nombre_completo} reabre la calle {calle.codigo}")
    await db.commit()
    resumen = await svc.resumen_calle(db, calle.id)
    await manager.broadcast(canal_layout(layout.id), "calle_actualizada",
                            {"id": calle.id, "codigo": calle.codigo, "estado": calle.estado, **resumen})
    return {"id_calle": calle.id, "estado": calle.estado}
