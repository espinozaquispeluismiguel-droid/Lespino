"""Equipos de trabajo y asignación de calles."""
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Equipo(TimestampMixin, Base):
    __tablename__ = "equipo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_delegacion: Mapped[int] = mapped_column(
        ForeignKey("delegacion.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    miembros: Mapped[list["EquipoUsuario"]] = relationship(
        back_populates="equipo", cascade="all, delete-orphan"
    )


class EquipoUsuario(Base):
    __tablename__ = "equipo_usuario"

    id_equipo: Mapped[int] = mapped_column(ForeignKey("equipo.id", ondelete="CASCADE"), primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    es_lider: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    fecha_alta: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    equipo: Mapped[Equipo] = relationship(back_populates="miembros")


class AsignacionCalle(Base):
    __tablename__ = "asignacion_calle"
    __table_args__ = (
        # Debe asignarse a un usuario, a un equipo, o a ambos
        CheckConstraint("id_usuario IS NOT NULL OR id_equipo IS NOT NULL", name="destinatario"),
        Index("ix_asignacion_calle_activa", "id_calle", "activa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_calle: Mapped[int] = mapped_column(ForeignKey("calle.id", ondelete="CASCADE"), nullable=False)
    id_usuario: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"), index=True)
    id_equipo: Mapped[int | None] = mapped_column(ForeignKey("equipo.id", ondelete="CASCADE"), index=True)
    id_usuario_asignador: Mapped[int | None] = mapped_column(ForeignKey("usuario.id", ondelete="SET NULL"))
    fecha_asignacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
