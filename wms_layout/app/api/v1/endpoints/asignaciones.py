"""Fase 3: asignación de calles a usuarios o equipos (supervisor)."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import supervisor_o_admin
from app.core.database import get_db
from app.models import AsignacionCalle, Calle, Equipo, EstadoCalle, RolUsuario, TipoEventoHistorial, Usuario
from app.schemas.almacen import AsignacionIn
from app.services.almacen_service import asignaciones_activas, obtener_calle
from app.services.historial_service import registrar_evento
from app.websockets.manager import canal_layout, manager

router = APIRouter(prefix="/asignaciones", tags=["Asignaciones"])


@router.post("", status_code=201)
async def asignar(data: AsignacionIn, db: AsyncSession = Depends(get_db), sup: Usuario = Depends(supervisor_o_admin)):
    destino = ""
    if data.id_usuario is not None:
        op = await db.get(Usuario, data.id_usuario)
        if op is None or op.id_delegacion != sup.id_delegacion or not op.activo:
            raise HTTPException(404, "Usuario no encontrado")
        if op.rol is not RolUsuario.OPERARIO:
            raise HTTPException(422, "Solo se asignan calles a operarios")
        destino = op.nombre_completo
    if data.id_equipo is not None:
        eq = await db.get(Equipo, data.id_equipo)
        if eq is None or eq.id_delegacion != sup.id_delegacion or not eq.activo:
            raise HTTPException(404, "Equipo no encontrado")
        destino = f"{destino} / equipo {eq.nombre}".strip(" /")

    layouts: set[int] = set()
    calles: list[Calle] = []
    for id_calle in dict.fromkeys(data.ids_calle):
        calle, layout = await obtener_calle(db, id_calle, sup)
        calles.append(calle)
        layouts.add(layout.id)

    ids = [c.id for c in calles]
    # Una sola asignación activa por calle: la nueva sustituye a la anterior
    await db.execute(
        update(AsignacionCalle)
        .where(AsignacionCalle.id_calle.in_(ids), AsignacionCalle.activa.is_(True))
        .values(activa=False)
        .execution_options(synchronize_session=False)
    )
    for c in calles:
        db.add(AsignacionCalle(id_calle=c.id, id_usuario=data.id_usuario, id_equipo=data.id_equipo,
                               id_usuario_asignador=sup.id))
        if c.estado is EstadoCalle.PENDIENTE:
            c.estado = EstadoCalle.ASIGNADA
        registrar_evento(db, id_calle=c.id, id_usuario=sup.id, id_equipo=data.id_equipo,
                         tipo=TipoEventoHistorial.CALLE_ASIGNADA,
                         descripcion=f"Calle {c.codigo} asignada a {destino}",
                         datos={"id_usuario": data.id_usuario, "id_equipo": data.id_equipo})
    await db.commit()

    asig = await asignaciones_activas(db, ids)
    for id_layout in layouts:
        await manager.broadcast(canal_layout(id_layout), "calles_asignadas", {
            "calles": [{"id": c.id, "codigo": c.codigo, "estado": c.estado,
                        "asignacion": asig[c.id].model_dump() if c.id in asig else None} for c in calles],
        })
    return {"asignadas": len(calles)}


@router.delete("/{id_asignacion}", status_code=204)
async def desasignar(id_asignacion: int, db: AsyncSession = Depends(get_db), sup: Usuario = Depends(supervisor_o_admin)):
    a = await db.get(AsignacionCalle, id_asignacion)
    if a is None or not a.activa:
        raise HTTPException(404, "Asignación no encontrada")
    calle, layout = await obtener_calle(db, a.id_calle, sup)
    a.activa = False
    otras = await db.scalar(
        select(AsignacionCalle.id).where(AsignacionCalle.id_calle == calle.id, AsignacionCalle.activa.is_(True),
                                         AsignacionCalle.id != a.id)
    )
    if not otras and calle.estado is EstadoCalle.ASIGNADA:
        calle.estado = EstadoCalle.PENDIENTE
    registrar_evento(db, id_calle=calle.id, id_usuario=sup.id, tipo=TipoEventoHistorial.CALLE_ASIGNADA,
                     descripcion=f"Calle {calle.codigo}: asignación retirada")
    await db.commit()
    await manager.broadcast(canal_layout(layout.id), "calles_asignadas",
                            {"calles": [{"id": calle.id, "codigo": calle.codigo, "estado": calle.estado,
                                         "asignacion": None}]})
    return Response(status_code=204)
