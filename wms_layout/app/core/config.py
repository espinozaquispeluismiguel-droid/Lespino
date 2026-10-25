"""Configuración centralizada (variables de entorno / .env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "WMS Layout & Inventario"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # PostgreSQL (driver asyncpg)
    DATABASE_URL: str = "postgresql+asyncpg://wms:wms@localhost:5432/wms_layout"
    DB_NULLPOOL: bool = False  # solo tests

    # Seguridad / JWT
    SECRET_KEY: str = "CAMBIAR-EN-PRODUCCION"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # un turno de 8 h
    MAX_INTENTOS_FALLIDOS: int = 5
    MINUTOS_BLOQUEO: int = 15

    # Carga Excel
    EXCEL_MAX_MB: int = 10
    EXCEL_CHUNK_SIZE: int = 1000

    # Inventario
    CONTEO_CIEGO: bool = True  # el operario no ve la cantidad teórica
    TOLERANCIA_CANTIDAD: float = 0.0  # diferencia absoluta admitida para considerar "coincide"

    # OCR
    TESSERACT_CMD: str | None = None
    OCR_IDIOMA: str = "spa+eng"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
