"""Estructura física del almacén: layout -> área -> calle."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import EstadoCalle, pg_enum


class Layout(TimestampMixin, Base):
    __tablename__ = "layout"
    __table_args__ = (UniqueConstraint("id_delegacion", "nombre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_delegacion: Mapped[int] = mapped_column(
        ForeignKey("delegacion.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    ancho: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # dimensiones del plano
    alto: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    id_usuario_creador: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))

    areas: Mapped[list["Area"]] = relationship(back_populates="layout", cascade="all, delete-orphan")


class Area(TimestampMixin, Base):
    __tablename__ = "area"
    __table_args__ = (UniqueConstraint("id_layout", "nombre"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_layout: Mapped[int] = mapped_column(
        ForeignKey("layout.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(80), nullable=False)  # "Muro", "Andamio"...
    color: Mapped[str | None] = mapped_column(String(9))  # #RRGGBB para el plano
    coord_x: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    coord_y: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    ancho: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    alto: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))

    layout: Mapped[Layout] = relationship(back_populates="areas")
    calles: Mapped[list["Calle"]] = relationship(back_populates="area", cascade="all, delete-orphan")


class Calle(TimestampMixin, Base):
    __tablename__ = "calle"
    __table_args__ = (UniqueConstraint("id_area", "codigo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_area: Mapped[int] = mapped_column(ForeignKey("area.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)  # "A1", "B1"...
    coord_x: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    coord_y: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    ancho: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    alto: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    rotacion: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))

    estado: Mapped[EstadoCalle] = mapped_column(
        pg_enum(EstadoCalle, "estado_calle"),
        default=EstadoCalle.PENDIENTE,
        server_default=EstadoCalle.PENDIENTE.value,
        nullable=False,
        index=True,
    )
    fecha_inicio_conteo: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fecha_verificacion: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    id_usuario_verificador: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))

    area: Mapped[Area] = relationship(back_populates="calles")
