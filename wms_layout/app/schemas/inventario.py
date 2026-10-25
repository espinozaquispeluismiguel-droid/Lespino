from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EstadoCalle, EstadoConteo, MetodoIngreso


class RegistroPaqueteIn(BaseModel):
    """Payload único para los 3 métodos de captura (manual, QR, foto IA)."""

    id_calle: int
    numero_de_paquete: str = Field(min_length=1, max_length=80)
    cantidad_contada: Decimal = Field(ge=0, max_digits=14, decimal_places=3)
    metodo_ingreso: MetodoIngreso = MetodoIngreso.MANUAL
    id_equipo: int | None = None
    # Opcionales: solo se usan si el paquete NO está catalogado (sobrante)
    articulo: str | None = Field(default=None, max_length=60)
    nombre: str | None = Field(default=None, max_length=255)
    unidad_de_medida: str | None = Field(default=None, max_length=20)
    observaciones: str | None = None
    ocr_confianza: Decimal | None = Field(default=None, ge=0, le=100)
    reconteo: bool = Field(
        default=False, description="True para sustituir un conteo vigente previo del mismo paquete"
    )

    @field_validator("numero_de_paquete")
    @classmethod
    def normalizar(cls, v: str) -> str:
        from app.services.normalizacion import normalizar_paquete

        v = normalizar_paquete(v)
        if not v:
            raise ValueError("numero_de_paquete vacío")
        return v


class AvanceLayout(BaseModel):
    id_layout: int
    total_catalogados: int
    contados: int
    coinciden: int
    diferencias: int
    no_catalogados: int
    porcentaje_avance: float


class ResultadoValidacion(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    id_calle: int
    codigo_calle: str
    numero_de_paquete: str
    estado: EstadoConteo
    coincide: bool
    cantidad_contada: Decimal
    cantidad_esperada: Decimal | None = None  # oculto al operario si CONTEO_CIEGO
    diferencia: Decimal | None = None
    articulo: str | None = None
    nombre: str | None = None
    unidad_de_medida: str | None = None
    metodo_ingreso: MetodoIngreso
    es_reconteo: bool = False
    estado_calle: EstadoCalle
    mensaje: str
    fecha_registro: datetime
    avance: AvanceLayout


class DatosOCR(BaseModel):
    """Propuesta extraída de la foto; el operario la confirma antes de registrar."""

    numero_de_paquete: str | None = None
    articulo: str | None = None
    cantidad: Decimal | None = None
    unidad_de_medida: str | None = None
    confianza: float = 0.0
    texto_crudo: str = ""
    producto_encontrado: bool = False
    nombre_catalogo: str | None = None


class FinalizarCalleOut(BaseModel):
    id_calle: int
    estado: EstadoCalle
    paquetes_contados: int
    diferencias: int
    no_catalogados: int
