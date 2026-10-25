"""Enumeraciones de dominio (se mapean a tipos ENUM nativos de PostgreSQL)."""
import enum


class RolUsuario(str, enum.Enum):
    ADMINISTRADOR = "administrador"
    SUPERVISOR = "supervisor"
    OPERARIO = "operario"


class EstadoCalle(str, enum.Enum):
    PENDIENTE = "pendiente"          # creada, sin asignar
    ASIGNADA = "asignada"            # tiene equipo/usuario asignado
    EN_PROCESO = "en_proceso"        # se ha registrado al menos un paquete
    VERIFICADA = "verificada"        # cerrada sin incidencias
    CON_INCIDENCIAS = "con_incidencias"  # cerrada con diferencias o sobrantes


class EstadoProducto(str, enum.Enum):
    ACTIVO = "activo"
    INACTIVO = "inactivo"


class EstadoConteo(str, enum.Enum):
    COINCIDE = "coincide"
    DIFERENCIA = "diferencia"
    NO_CATALOGADO = "no_catalogado"  # No Catalogado / Sobrante


class MetodoIngreso(str, enum.Enum):
    MANUAL = "manual"
    QR = "qr"
    FOTO_IA = "foto_ia"


class TipoEventoHistorial(str, enum.Enum):
    CALLE_CREADA = "calle_creada"
    CALLE_ASIGNADA = "calle_asignada"
    INICIO_CONTEO = "inicio_conteo"
    PAQUETE_REGISTRADO = "paquete_registrado"
    PAQUETE_RECONTADO = "paquete_recontado"
    PAQUETE_NO_CATALOGADO = "paquete_no_catalogado"
    CALLE_FINALIZADA = "calle_finalizada"
    CALLE_REABIERTA = "calle_reabierta"


def pg_enum(enum_cls: type[enum.Enum], name: str):
    """ENUM nativo que guarda el *valor* (minúsculas) y no el nombre del miembro."""
    from sqlalchemy import Enum

    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
