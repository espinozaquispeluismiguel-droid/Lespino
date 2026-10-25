"""Fase 2: carga masiva del maestro de productos desde Excel."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import solo_admin
from app.core.config import settings
from app.core.database import get_db
from app.models import Usuario
from app.services.almacen_service import obtener_layout
from app.schemas.producto import ModoImportacion, ResultadoImportacion
from app.services.excel_import import ExcelFormatoError, generar_plantilla, importar_productos_excel

router = APIRouter(prefix="/productos", tags=["Productos (maestro)"])

EXTENSIONES = (".xlsx", ".xlsm")


@router.post(
    "/importar",
    response_model=ResultadoImportacion,
    summary="Carga masiva de productos desde Excel",
    description=(
        "Columnas obligatorias: articulo, nombre, numero_de_paquete, cantidad. "
        "Opcionales: unidad_de_medida (def. UND), estado (activo/inactivo). "
        "Se aceptan alias de cabecera (p.ej. 'Nº Paquete', 'Descripción', 'UM')."
    ),
)
async def importar_productos(
    id_layout: int = Form(...),
    modo: ModoImportacion = Form(ModoImportacion.UPSERT),
    dry_run: bool = Form(False, description="Solo valida; no guarda nada"),
    permitir_parcial: bool = Form(True, description="Si False, cualquier error revierte toda la carga"),
    archivo: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(solo_admin),
):
    nombre = archivo.filename or "archivo.xlsx"
    if not nombre.lower().endswith(EXTENSIONES):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"Formato no admitido. Use {EXTENSIONES}")

    limite = settings.EXCEL_MAX_MB * 1024 * 1024
    contenido = await archivo.read(limite + 1)
    if len(contenido) > limite:
        raise HTTPException(413, f"El archivo supera {settings.EXCEL_MAX_MB} MB")
    if not contenido:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Archivo vacío")

    layout = await obtener_layout(db, id_layout, _admin)
    if not layout.activo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Layout {id_layout} inactivo")

    try:
        return await importar_productos_excel(
            db,
            contenido=contenido,
            nombre_archivo=nombre,
            id_layout=id_layout,
            modo=modo,
            dry_run=dry_run,
            permitir_parcial=permitir_parcial,
        )
    except ExcelFormatoError as exc:
        raise HTTPException(422, str(exc))


@router.get("/plantilla", summary="Descargar plantilla Excel de ejemplo")
async def descargar_plantilla(_admin: Usuario = Depends(solo_admin)):
    return Response(
        content=generar_plantilla(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_productos.xlsx"'},
    )
