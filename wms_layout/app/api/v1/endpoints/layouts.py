"""Fase 2: gestión de layouts, áreas y calles."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import cualquier_rol, solo_admin, supervisor_o_admin
from app.core.database import get_db
from app.models import Area, Calle, Layout, TipoEventoHistorial, Usuario
from app.schemas.almacen import AreaIn, AreaOut, CalleOut, CallesIn, CalleUpdate, LayoutDetalle, LayoutIn, LayoutOut
from app.services.almacen_service import detalle_layout, obtener_calle, obtener_layout
from app.services.historial_service import registrar_evento
from app.services.inventario_service import calcular_avance_layout
from app.schemas.inventario import AvanceLayout

router = APIRouter(tags=["Layouts / Áreas / Calles"])

SEP_AREAS = Decimal("70")   # separación vertical por defecto entre áreas en el plano
PASO_CALLE = Decimal("12")  # separación horizontal por defecto entre calles


async def _commit(db: AsyncSession, msg: str):
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, msg)


@router.get("/layouts", response_model=list[LayoutOut])
async def listar_layouts(db: AsyncSession = Depends(get_db), u: Usuario = Depends(cualquier_rol)):
    n_areas = select(func.count(Area.id)).where(Area.id_layout == Layout.id).scalar_subquery()
    n_calles = (
        select(func.count(Calle.id)).join(Area, Area.id == Calle.id_area).where(Area.id_layout == Layout.id)
    ).scalar_subquery()
    rows = (
        await db.execute(
            select(Layout, n_areas, n_calles)
            .where(Layout.id_delegacion == u.id_delegacion)
            .order_by(Layout.nombre)
        )
    ).all()
    return [
        LayoutOut(id=l.id, nombre=l.nombre, descripcion=l.descripcion, activo=l.activo, n_areas=a, n_calles=c)
        for l, a, c in rows
    ]


@router.post("/layouts", response_model=LayoutOut, status_code=201)
async def crear_layout(data: LayoutIn, db: AsyncSession = Depends(get_db), u: Usuario = Depends(solo_admin)):
    layout = Layout(id_delegacion=u.id_delegacion, nombre=data.nombre.strip(), descripcion=data.descripcion,
                    id_usuario_creador=u.id)
    db.add(layout)
    await _commit(db, f"Ya existe un layout llamado '{data.nombre}'")
    return LayoutOut(id=layout.id, nombre=layout.nombre, descripcion=layout.descripcion, activo=True)


@router.get("/layouts/{id_layout}", response_model=LayoutDetalle)
async def obtener_detalle(id_layout: int, db: AsyncSession = Depends(get_db), u: Usuario = Depends(supervisor_o_admin)):
    return await detalle_layout(db, await obtener_layout(db, id_layout, u))


@router.get("/layouts/{id_layout}/avance", response_model=AvanceLayout)
async def avance(id_layout: int, db: AsyncSession = Depends(get_db), u: Usuario = Depends(supervisor_o_admin)):
    await obtener_layout(db, id_layout, u)
    return await calcular_avance_layout(db, id_layout)


@router.post("/layouts/{id_layout}/areas", response_model=AreaOut, status_code=201)
async def crear_area(id_layout: int, data: AreaIn, db: AsyncSession = Depends(get_db), u: Usuario = Depends(solo_admin)):
    await obtener_layout(db, id_layout, u)
    n = await db.scalar(select(func.count(Area.id)).where(Area.id_layout == id_layout)) or 0
    area = Area(
        id_layout=id_layout, nombre=data.nombre.strip(), color=data.color,
        coord_x=data.coord_x if data.coord_x is not None else Decimal("0"),
        coord_y=data.coord_y if data.coord_y is not None else SEP_AREAS * n,
    )
    db.add(area)
    await _commit(db, f"Ya existe un área '{data.nombre}' en este layout")
    return AreaOut(id=area.id, nombre=area.nombre, color=area.color, coord_x=float(area.coord_x),
                   coord_y=float(area.coord_y))


@router.delete("/areas/{id_area}", status_code=204)
async def borrar_area(id_area: int, db: AsyncSession = Depends(get_db), u: Usuario = Depends(solo_admin)):
    area = await db.get(Area, id_area)
    if area is None:
        raise HTTPException(404, "Área no encontrada")
    await obtener_layout(db, area.id_layout, u)
    await db.delete(area)
    await _commit(db, "No se puede borrar: alguna calle del área ya tiene conteos registrados")
    return Response(status_code=204)


@router.post("/areas/{id_area}/calles", response_model=list[CalleOut], status_code=201)
async def crear_calles(id_area: int, data: CallesIn, db: AsyncSession = Depends(get_db), u: Usuario = Depends(solo_admin)):
    area = await db.get(Area, id_area)
    if area is None:
        raise HTTPException(404, "Área no encontrada")
    await obtener_layout(db, area.id_layout, u)
    codigos = data.lista()
    existentes = set((await db.scalars(select(Calle.codigo).where(Calle.id_area == id_area))).all())
    repetidas = [c for c in codigos if c in existentes]
    if repetidas or len(set(codigos)) != len(codigos):
        raise HTTPException(409, f"Códigos repetidos: {sorted(set(repetidas)) or 'duplicados en la petición'}")

    n = len(existentes)
    x0, y0 = Decimal(area.coord_x or 0), Decimal(area.coord_y or 0)
    paso = max(PASO_CALLE, data.ancho + 4)
    nuevas = [
        Calle(id_area=id_area, codigo=c, ancho=data.ancho, alto=data.alto,
              coord_x=x0 + 4 + paso * (n + i), coord_y=y0 + 12)
        for i, c in enumerate(codigos)
    ]
    db.add_all(nuevas)
    await db.flush()
    for c in nuevas:
        registrar_evento(db, id_calle=c.id, id_usuario=u.id, tipo=TipoEventoHistorial.CALLE_CREADA,
                         descripcion=f"Calle {c.codigo} creada en el área {area.nombre}")
    await _commit(db, "Conflicto al crear calles")
    return [
        CalleOut(id=c.id, id_area=c.id_area, codigo=c.codigo, coord_x=float(c.coord_x), coord_y=float(c.coord_y),
                 ancho=float(c.ancho), alto=float(c.alto), estado=c.estado)
        for c in nuevas
    ]


@router.patch("/calles/{id_calle}", response_model=CalleOut)
async def editar_calle(id_calle: int, data: CalleUpdate, db: AsyncSession = Depends(get_db),
                       u: Usuario = Depends(solo_admin)):
    calle, _ = await obtener_calle(db, id_calle, u)
    for campo, valor in data.model_dump(exclude_unset=True).items():
        setattr(calle, campo, valor.strip().upper() if campo == "codigo" and valor else valor)
    await _commit(db, "Ya existe una calle con ese código en el área")
    f = lambda v: float(v) if v is not None else None  # noqa: E731
    return CalleOut(id=calle.id, id_area=calle.id_area, codigo=calle.codigo, coord_x=f(calle.coord_x),
                    coord_y=f(calle.coord_y), ancho=f(calle.ancho), alto=f(calle.alto), estado=calle.estado)


@router.delete("/calles/{id_calle}", status_code=204)
async def borrar_calle(id_calle: int, db: AsyncSession = Depends(get_db), u: Usuario = Depends(solo_admin)):
    calle, _ = await obtener_calle(db, id_calle, u)
    await db.delete(calle)
    await _commit(db, "No se puede borrar: la calle ya tiene conteos registrados")
    return Response(status_code=204)
