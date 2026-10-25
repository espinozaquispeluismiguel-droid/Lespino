"""Consultas de lectura del almacén compartidas por varios endpoints."""
from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Area,
    AsignacionCalle,
    Calle,
    Equipo,
    EstadoConteo,
    Layout,
    ProductoInventario,
    Usuario,
)
from app.schemas.almacen import AreaOut, AsignacionBreve, CalleOut, LayoutDetalle


def _f(v):
    return float(v) if v is not None else None


async def obtener_layout(db: AsyncSession, id_layout: int, usuario: Usuario) -> Layout:
    """Layout de la delegación del usuario (aislamiento entre delegaciones)."""
    layout = await db.get(Layout, id_layout)
    if layout is None or layout.id_delegacion != usuario.id_delegacion:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Layout {id_layout} no encontrado")
    return layout


async def obtener_calle(db: AsyncSession, id_calle: int, usuario: Usuario) -> tuple[Calle, Layout]:
    row = (
        await db.execute(
            select(Calle, Layout)
            .join(Area, Area.id == Calle.id_area)
            .join(Layout, Layout.id == Area.id_layout)
            .where(Calle.id == id_calle)
        )
    ).first()
    if row is None or row[1].id_delegacion != usuario.id_delegacion:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Calle {id_calle} no encontrada")
    return row[0], row[1]


async def stats_por_calle(db: AsyncSession, ids_calle: list[int]) -> dict[int, dict]:
    if not ids_calle:
        return {}
    pi = ProductoInventario
    rows = (
        await db.execute(
            select(
                pi.id_calle,
                func.count(pi.id),
                func.coalesce(func.sum(case((pi.estado == EstadoConteo.DIFERENCIA, 1), else_=0)), 0),
                func.coalesce(func.sum(case((pi.estado == EstadoConteo.NO_CATALOGADO, 1), else_=0)), 0),
            )
            .where(pi.id_calle.in_(ids_calle), pi.vigente.is_(True))
            .group_by(pi.id_calle)
        )
    ).all()
    return {
        r[0]: {"paquetes_contados": int(r[1]), "diferencias": int(r[2]), "no_catalogados": int(r[3])} for r in rows
    }


async def asignaciones_activas(db: AsyncSession, ids_calle: list[int]) -> dict[int, AsignacionBreve]:
    if not ids_calle:
        return {}
    rows = (
        await db.execute(
            select(AsignacionCalle, Usuario.nombre_completo, Equipo.nombre)
            .outerjoin(Usuario, Usuario.id == AsignacionCalle.id_usuario)
            .outerjoin(Equipo, Equipo.id == AsignacionCalle.id_equipo)
            .where(AsignacionCalle.id_calle.in_(ids_calle), AsignacionCalle.activa.is_(True))
            .order_by(AsignacionCalle.fecha_asignacion)
        )
    ).all()
    out: dict[int, AsignacionBreve] = {}
    for a, usuario, equipo in rows:  # la más reciente prevalece
        out[a.id_calle] = AsignacionBreve(
            id=a.id, id_usuario=a.id_usuario, usuario=usuario, id_equipo=a.id_equipo, equipo=equipo
        )
    return out


async def detalle_layout(db: AsyncSession, layout: Layout) -> LayoutDetalle:
    areas = (await db.scalars(select(Area).where(Area.id_layout == layout.id).order_by(Area.id))).all()
    calles = (
        await db.scalars(
            select(Calle).where(Calle.id_area.in_([a.id for a in areas] or [-1])).order_by(Calle.id_area, Calle.id)
        )
    ).all()
    ids = [c.id for c in calles]
    stats = await stats_por_calle(db, ids)
    asig = await asignaciones_activas(db, ids)

    por_area: dict[int, list[CalleOut]] = {a.id: [] for a in areas}
    for c in calles:
        por_area[c.id_area].append(
            CalleOut(
                id=c.id, id_area=c.id_area, codigo=c.codigo, coord_x=_f(c.coord_x), coord_y=_f(c.coord_y),
                ancho=_f(c.ancho), alto=_f(c.alto), estado=c.estado, asignacion=asig.get(c.id),
                **stats.get(c.id, {}),
            )
        )
    return LayoutDetalle(
        id=layout.id,
        nombre=layout.nombre,
        descripcion=layout.descripcion,
        areas=[
            AreaOut(id=a.id, nombre=a.nombre, color=a.color, coord_x=_f(a.coord_x), coord_y=_f(a.coord_y),
                    calles=por_area[a.id])
            for a in areas
        ],
    )
