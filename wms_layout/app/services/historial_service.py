from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HistorialCalle, TipoEventoHistorial


def registrar_evento(
    db: AsyncSession,
    *,
    id_calle: int,
    tipo: TipoEventoHistorial,
    descripcion: str,
    id_usuario: int | None = None,
    id_equipo: int | None = None,
    id_producto_inventario: int | None = None,
    numero_de_paquete: str | None = None,
    datos: dict | None = None,
) -> HistorialCalle:
    """Añade el evento a la sesión. Se persiste en el MISMO commit que la operación
    de negocio, así nunca hay un conteo sin su traza (ni una traza huérfana)."""
    evento = HistorialCalle(
        id_calle=id_calle,
        id_usuario=id_usuario,
        id_equipo=id_equipo,
        id_producto_inventario=id_producto_inventario,
        tipo_evento=tipo,
        descripcion=descripcion,
        numero_de_paquete=numero_de_paquete,
        datos=datos,
    )
    db.add(evento)
    return evento
