"""Catálogo maestro (producto) y registro de conteo (producto_inventario)."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, BigIntPK, TimestampMixin
from app.models.enums import EstadoConteo, EstadoProducto, MetodoIngreso, pg_enum


class Producto(TimestampMixin, Base):
    """Maestro teórico. Se alimenta por carga masiva de Excel."""

    __tablename__ = "producto"
    __table_args__ = (
        CheckConstraint("cantidad >= 0", name="cantidad_no_negativa"),
        Index("ix_producto_layout_articulo", "id_layout", "articulo"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    id_layout: Mapped[int] = mapped_column(ForeignKey("layout.id", ondelete="CASCADE"), nullable=False)
    articulo: Mapped[str] = mapped_column(String(60), nullable=False)
    nombre: Mapped[str] = mapped_column(String(255), nullable=False)
    numero_de_paquete: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    estado: Mapped[EstadoProducto] = mapped_column(
        pg_enum(EstadoProducto, "estado_producto"),
        default=EstadoProducto.ACTIVO,
        server_default=EstadoProducto.ACTIVO.value,
        nullable=False,
    )
    unidad_de_medida: Mapped[str] = mapped_column(String(20), nullable=False, default="UND", server_default="UND")


class ProductoInventario(Base):
    """Cada fila = un paquete contado físicamente en una calle."""

    __tablename__ = "producto_inventario"
    __table_args__ = (
        CheckConstraint("cantidad_contada >= 0", name="contada_no_negativa"),
        Index("ix_prodinv_calle_fecha", "id_calle", "fecha_registro"),
        Index("ix_prodinv_paquete_vigente", "numero_de_paquete", "vigente"),
        Index("ix_prodinv_usuario_fecha", "id_usuario", "fecha_registro"),
        # Un paquete solo puede tener UN conteo vigente por calle (a nivel BD).
        # La regla "uno por layout" la garantiza el servicio con advisory lock.
        Index(
            "uq_prodinv_calle_paquete_vigente",
            "id_calle",
            "numero_de_paquete",
            unique=True,
            postgresql_where=text("vigente"),
            sqlite_where=text("vigente = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True)
    id_calle: Mapped[int] = mapped_column(ForeignKey("calle.id", ondelete="RESTRICT"), nullable=False)
    id_usuario: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=False)
    id_equipo: Mapped[int | None] = mapped_column(ForeignKey("equipo.id", ondelete="SET NULL"))
    id_producto: Mapped[int | None] = mapped_column(
        ForeignKey("producto.id", ondelete="SET NULL"), index=True
    )  # NULL => No catalogado / Sobrante

    articulo: Mapped[str | None] = mapped_column(String(60))
    nombre: Mapped[str | None] = mapped_column(String(255))
    numero_de_paquete: Mapped[str] = mapped_column(String(80), nullable=False)
    cantidad_contada: Mapped[Decimal] = mapped_column(Numeric(14, 3), nullable=False)
    cantidad_esperada: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    coincide: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    estado: Mapped[EstadoConteo] = mapped_column(pg_enum(EstadoConteo, "estado_conteo"), nullable=False)
    unidad_de_medida: Mapped[str | None] = mapped_column(String(20))
    metodo_ingreso: Mapped[MetodoIngreso] = mapped_column(
        pg_enum(MetodoIngreso, "metodo_ingreso"), nullable=False
    )

    # Trazabilidad de reconteos: el registro sustituido queda con vigente = false
    vigente: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    id_reemplaza_a: Mapped[int | None] = mapped_column(ForeignKey("producto_inventario.id", ondelete="SET NULL"))
    observaciones: Mapped[str | None] = mapped_column(Text)
    ocr_confianza: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # solo metodo foto_ia

    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    producto: Mapped[Producto | None] = relationship()
