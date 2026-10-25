"""Trazabilidad / auditoría por calle."""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BigIntPK, JSONType
from app.models.enums import TipoEventoHistorial, pg_enum


class HistorialCalle(Base):
    __tablename__ = "historial_calle"
    __table_args__ = (
        Index("ix_historial_calle_fecha", "id_calle", "fecha"),
        Index("ix_historial_usuario_fecha", "id_usuario", "fecha"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    id_calle: Mapped[int] = mapped_column(ForeignKey("calle.id", ondelete="CASCADE"), nullable=False)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    id_equipo: Mapped[int | None] = mapped_column(ForeignKey("equipo.id", ondelete="SET NULL"))
    id_producto_inventario: Mapped[int | None] = mapped_column(
        ForeignKey("producto_inventario.id", ondelete="SET NULL")
    )
    tipo_evento: Mapped[TipoEventoHistorial] = mapped_column(
        pg_enum(TipoEventoHistorial, "tipo_evento_historial"), nullable=False
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    datos: Mapped[dict | None] = mapped_column(JSONType)  # snapshot del evento
    numero_de_paquete: Mapped[str | None] = mapped_column(Text, index=True)  # filtro rápido de auditoría
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
