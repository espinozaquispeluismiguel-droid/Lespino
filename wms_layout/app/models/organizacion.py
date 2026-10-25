"""Organización, delegación y usuario."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import RolUsuario, pg_enum


class Organizacion(TimestampMixin, Base):
    __tablename__ = "organizacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    identificador_fiscal: Mapped[str | None] = mapped_column(String(30), unique=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    delegaciones: Mapped[list["Delegacion"]] = relationship(back_populates="organizacion")


class Delegacion(TimestampMixin, Base):
    __tablename__ = "delegacion"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_organizacion: Mapped[int] = mapped_column(
        ForeignKey("organizacion.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(150), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    organizacion: Mapped[Organizacion] = relationship(back_populates="delegaciones")
    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="delegacion")


class Usuario(TimestampMixin, Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    id_delegacion: Mapped[int] = mapped_column(
        ForeignKey("delegacion.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    username: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), unique=True)
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[RolUsuario] = mapped_column(pg_enum(RolUsuario, "rol_usuario"), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # Control de fuerza bruta
    intentos_fallidos: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False
    )
    bloqueado: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    bloqueado_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    delegacion: Mapped[Delegacion] = relationship(back_populates="usuarios")
