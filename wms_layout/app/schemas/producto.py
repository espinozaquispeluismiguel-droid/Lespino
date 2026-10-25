from enum import Enum

from pydantic import BaseModel, Field


class ModoImportacion(str, Enum):
    UPSERT = "upsert"          # inserta nuevos y actualiza existentes
    REEMPLAZAR = "reemplazar"  # además, inactiva los productos del layout que no vienen en el archivo


class ErrorFila(BaseModel):
    fila: int = Field(description="Número de fila en el Excel (1 = cabecera)")
    numero_de_paquete: str | None = None
    errores: list[str]


class ResultadoImportacion(BaseModel):
    id_layout: int
    archivo: str
    modo: ModoImportacion
    dry_run: bool
    aplicado: bool = Field(description="False si fue dry_run o se revirtió por errores")
    total_filas: int
    filas_validas: int
    insertados: int = 0
    actualizados: int = 0
    sin_cambios: int = 0
    inactivados: int = 0
    filas_con_error: int = 0
    errores: list[ErrorFila] = []
    errores_truncados: bool = False
    duracion_ms: int = 0
