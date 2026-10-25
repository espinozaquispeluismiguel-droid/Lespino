"""Importa todos los modelos para que Base.metadata los conozca (Alembic / create_all)."""
from app.models.almacen import Area, Calle, Layout
from app.models.base import Base
from app.models.enums import (
    EstadoCalle,
    EstadoConteo,
    EstadoProducto,
    MetodoIngreso,
    RolUsuario,
    TipoEventoHistorial,
)
from app.models.equipo import AsignacionCalle, Equipo, EquipoUsuario
from app.models.historial import HistorialCalle
from app.models.organizacion import Delegacion, Organizacion, Usuario
from app.models.producto import Producto, ProductoInventario

__all__ = [
    "Base",
    "Organizacion", "Delegacion", "Usuario",
    "Layout", "Area", "Calle",
    "Equipo", "EquipoUsuario", "AsignacionCalle",
    "Producto", "ProductoInventario",
    "HistorialCalle",
    "RolUsuario", "EstadoCalle", "EstadoProducto", "EstadoConteo", "MetodoIngreso", "TipoEventoHistorial",
]
