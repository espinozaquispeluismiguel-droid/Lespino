"""Fase 5: histórico de auditoría con filtros."""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import supervisor_o_admin
from app.core.database import get_db
from app.models import Calle, HistorialCalle, TipoEventoHistorial, Usuario

router = APIRouter(prefix="/historial", tags=["Auditoría"])


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: datetime
    tipo_evento: TipoEventoHistorial
    id_calle: int
    codigo_calle: str
    id_usuario: int | None
    usuario: str | None
    numero_de_paquete: str | None
    descripcion: str
    datos: dict | None


class PaginaEventos(BaseModel):
    total: int
    items: list[EventoOut]


@router.get("", response_model=PaginaEventos)
async def listar_historial(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    id_usuario: int | None = None,
    id_calle: int | None = None,
    numero_de_paquete: str | None = None,
    tipo_evento: TipoEventoHistorial | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    _s: Usuario = Depends(supervisor_o_admin),
):
    h = HistorialCalle
    filtros = []
    if desde:
        filtros.append(h.fecha >= desde)
    if hasta:
        filtros.append(h.fecha <= hasta)
    if id_usuario:
        filtros.append(h.id_usuario == id_usuario)
    if id_calle:
        filtros.append(h.id_calle == id_calle)
    if numero_de_paquete:
        filtros.append(h.numero_de_paquete == numero_de_paquete.strip().upper())
    if tipo_evento:
        filtros.append(h.tipo_evento == tipo_evento)

    total = await db.scalar(select(func.count(h.id)).where(*filtros))
    rows = (
        await db.execute(
            select(h, Calle.codigo, Usuario.nombre_completo)
            .join(Calle, Calle.id == h.id_calle)
            .outerjoin(Usuario, Usuario.id == h.id_usuario)
            .where(*filtros)
            .order_by(h.fecha.desc(), h.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    items = [
        EventoOut(
            id=e.id, fecha=e.fecha, tipo_evento=e.tipo_evento, id_calle=e.id_calle, codigo_calle=codigo,
            id_usuario=e.id_usuario, usuario=nombre, numero_de_paquete=e.numero_de_paquete,
            descripcion=e.descripcion, datos=e.datos,
        )
        for e, codigo, nombre in rows
    ]
    return PaginaEventos(total=total or 0, items=items)
