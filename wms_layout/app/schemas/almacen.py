from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import EstadoCalle, RolUsuario


# ----------------------------------------------------------------- layout / área / calle
class LayoutIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    descripcion: str | None = None


class LayoutOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    activo: bool
    n_areas: int = 0
    n_calles: int = 0


class AreaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    color: str | None = Field(default=None, max_length=9)
    coord_x: Decimal | None = None
    coord_y: Decimal | None = None


class CallesIn(BaseModel):
    """Lista explícita de códigos o generador prefijo+rango (A1..A10)."""

    codigos: list[str] | None = None
    prefijo: str | None = Field(default=None, max_length=10)
    desde: int | None = Field(default=None, ge=0)
    hasta: int | None = Field(default=None, ge=0)
    ancho: Decimal = Decimal("8")
    alto: Decimal = Decimal("40")

    @model_validator(mode="after")
    def _uno_de_dos(self):
        if not self.codigos and not (self.prefijo is not None and self.desde is not None and self.hasta is not None):
            raise ValueError("Indique 'codigos' o 'prefijo' + 'desde' + 'hasta'")
        if self.desde is not None and self.hasta is not None and self.hasta < self.desde:
            raise ValueError("'hasta' debe ser >= 'desde'")
        if self.desde is not None and self.hasta is not None and self.hasta - self.desde > 200:
            raise ValueError("Máximo 200 calles por operación")
        return self

    def lista(self) -> list[str]:
        if self.codigos:
            return [c.strip().upper() for c in self.codigos if c.strip()]
        return [f"{self.prefijo.strip().upper()}{i}" for i in range(self.desde, self.hasta + 1)]


class CalleUpdate(BaseModel):
    codigo: str | None = Field(default=None, max_length=20)
    coord_x: Decimal | None = None
    coord_y: Decimal | None = None
    ancho: Decimal | None = None
    alto: Decimal | None = None


class AsignacionBreve(BaseModel):
    id: int
    id_usuario: int | None
    usuario: str | None
    id_equipo: int | None
    equipo: str | None


class CalleOut(BaseModel):
    id: int
    id_area: int
    codigo: str
    coord_x: float | None
    coord_y: float | None
    ancho: float | None
    alto: float | None
    estado: EstadoCalle
    asignacion: AsignacionBreve | None = None
    paquetes_contados: int = 0
    diferencias: int = 0
    no_catalogados: int = 0


class AreaOut(BaseModel):
    id: int
    nombre: str
    color: str | None
    coord_x: float | None
    coord_y: float | None
    calles: list[CalleOut] = []


class LayoutDetalle(BaseModel):
    id: int
    nombre: str
    descripcion: str | None
    areas: list[AreaOut]


# ----------------------------------------------------------------- asignaciones
class AsignacionIn(BaseModel):
    ids_calle: list[int] = Field(min_length=1)
    id_usuario: int | None = None
    id_equipo: int | None = None

    @model_validator(mode="after")
    def _destino(self):
        if self.id_usuario is None and self.id_equipo is None:
            raise ValueError("Indique id_usuario o id_equipo")
        return self


# ----------------------------------------------------------------- usuarios / equipos
class UsuarioOut(BaseModel):
    id: int
    username: str
    nombre_completo: str
    email: str | None
    rol: RolUsuario
    activo: bool
    bloqueado: bool
    ultimo_acceso: datetime | None


class UsuarioIn(BaseModel):
    username: str = Field(min_length=3, max_length=60)
    nombre_completo: str = Field(min_length=1, max_length=150)
    email: str | None = None
    rol: RolUsuario
    password: str = Field(min_length=8, max_length=128)


class EquipoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    miembros: list[int] = []


class MiembroOut(BaseModel):
    id_usuario: int
    nombre_completo: str
    es_lider: bool


class EquipoOut(BaseModel):
    id: int
    nombre: str
    activo: bool
    miembros: list[MiembroOut] = []


class MiCalleOut(BaseModel):
    id_calle: int
    codigo: str
    area: str
    id_layout: int
    layout: str
    estado: EstadoCalle
    equipo: str | None
    paquetes_contados: int
